"""Main desktop window and shared application state."""

from __future__ import annotations

import queue
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from app.config.settings import load_settings, save_settings
from app.config.theme import DEFAULT_THEME
from app.services.media_provider import YtDlpMediaProvider
from app.services.video_preview import is_vlc_available
from app.ui.download_controller import DownloadControllerMixin
from app.ui.layout import LayoutMixin
from app.ui.settings_window import SettingsWindow
from app.ui.theme import ThemeMixin


class AudioPlaylistDownloader(ThemeMixin, LayoutMixin, DownloadControllerMixin):
    """Initialize shared state; focused mixins provide UI and interactions."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("youMP3gmr")
        self.app_icon_path = Path(__file__).resolve().parents[2] / "youMP3gmr.ico"
        if self.app_icon_path.is_file():
            self.root.iconbitmap(str(self.app_icon_path))
        self.root.minsize(960, 720)
        self.theme = DEFAULT_THEME
        self.palette = self._get_palette()
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.media_provider = YtDlpMediaProvider()
        self.rounded_buttons = []
        music_directory = Path.home() / "Music"
        default_directory = music_directory if music_directory.is_dir() else Path.home()
        settings, settings_error = load_settings(default_directory)
        self.output_directory = tk.StringVar(value=str(settings["output_directory"]))
        self.preview_resolution = tk.StringVar(
            value=str(settings["preview_resolution"])
        )
        self.preview_volume = int(settings["preview_volume"])
        self.concurrent_downloads = int(settings["concurrent_downloads"])
        self.music_styles = list(settings["music_styles"])
        self.search_queue_sidebar_widgets: list[
            tuple[dict[str, Any], tk.StringVar, ttk.Combobox]
        ] = []
        self._settings_error = settings_error
        self._settings_window: SettingsWindow | None = None
        self.url = tk.StringVar()
        self.download_mode = tk.StringVar(value="single")
        self.status = tk.StringVar(value="Pega un enlace para comenzar.")
        self.items: list[dict[str, Any]] = []
        self.item_widgets: list[dict[str, Any]] = []
        self.search_queue: list[dict[str, Any]] = []
        self.search_results: list[dict[str, Any]] = []
        self.search_query = tk.StringVar()
        self._search_generation = 0
        self._search_view = "results"
        self._search_query = ""
        self._loading = False
        self.metadata_ready = False
        self.downloading = False
        self.details_visible = False
        self.clip_section: tuple[float, float] | None = None
        self.clip_editor_window = None
        self.search_preview_window = None
        self._search_preview_loading = False
        self._search_preview_generation = 0
        self._preview_loading = False
        self._vlc_available = is_vlc_available()
        self._vlc_installing = False
        self._vlc_install_complete = False
        self._restore_geometry: str | None = None
        self._build_interface()
        self._apply_theme()
        self.root.update_idletasks()
        self.initial_geometry = self.root.geometry()
        self.root.pack_propagate(False)
        self.root.geometry(self.initial_geometry)
        self._remove_native_title_bar()
        self._update_empty_state()
        self._update_clip_editor_button()
        self.download_all_button.configure(state="disabled")
        self.bottom_action_button.configure(state="disabled")
        if self._settings_error:
            self._append_log(self._settings_error)
            messagebox.showwarning(
                "Preferencias no disponibles",
                f"{self._settings_error}\nSe usarán los valores predeterminados.",
                parent=self.root,
            )
        self.url.trace_add("write", self._on_url_changed)
        self.root.after(100, self._process_messages)

    def _remove_native_title_bar(self) -> None:
        """Remove Windows caption and border so the app surface reaches the top edge."""
        if sys.platform != "win32":
            return

        self.root.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user32.SetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_long,
        ]
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
        if not hwnd:
            raise OSError("No se pudo localizar la ventana principal de Windows.")

        style = user32.GetWindowLongW(hwnd, -16)
        style &= ~(0x00C00000 | 0x00040000 | 0x00800000)
        user32.SetWindowLongW(hwnd, -16, style)
        user32.GetWindowLongW.restype = ctypes.c_long
        extended_style = user32.GetWindowLongW(hwnd, -20)
        extended_style &= ~0x00000200
        user32.SetWindowLongW(hwnd, -20, extended_style)
        if not user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0027):
            raise OSError("No se pudo actualizar el marco de la ventana.")

    def _start_window_drag(self, _event: tk.Event) -> None:
        if self.root.state() == "zoomed":
            return
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
            release_capture = user32.ReleaseCapture
            release_capture.argtypes = []
            release_capture.restype = wintypes.BOOL
            post_message = user32.PostMessageW
            post_message.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            post_message.restype = wintypes.BOOL
            release_capture()
            if not post_message(hwnd, 0x00A1, 2, 0):
                raise OSError("Windows no pudo iniciar el movimiento de la ventana.")

    def _minimize_window(self) -> None:
        self.root.iconify()

    def _open_settings(self) -> None:
        if self._settings_window is not None:
            try:
                if self._settings_window.window.winfo_exists():
                    self._settings_window.window.lift()
                    return
            except tk.TclError:
                self._settings_window = None
        self._settings_window = SettingsWindow(
            self.root,
            self.output_directory.get(),
            self.preview_resolution.get(),
            self.preview_volume,
            self.concurrent_downloads,
            self.music_styles,
            self._save_settings,
        )

    def _save_settings(
        self,
        output_directory: str,
        preview_resolution: str,
        preview_volume: int,
        concurrent_downloads: int,
        music_styles: list[str],
    ) -> bool:
        try:
            save_settings(
                output_directory,
                preview_resolution,
                preview_volume,
                concurrent_downloads,
                music_styles,
            )
        except (OSError, ValueError) as error:
            self._append_log(f"No se pudieron guardar los ajustes: {error}")
            messagebox.showerror(
                "No se pudieron guardar los ajustes",
                str(error),
                parent=self.root,
            )
            return False
        self.output_directory.set(output_directory)
        self.preview_resolution.set(preview_resolution)
        self.preview_volume = preview_volume
        self.concurrent_downloads = concurrent_downloads
        self.music_styles = music_styles.copy()
        for widgets in self.item_widgets:
            item = widgets.get("item")
            if item is None:
                continue
            if item.get("music_style") not in self.music_styles:
                item["music_style"] = ""
            style_variable = widgets.get("music_style_value")
            style_combo = widgets.get("music_style_combo")
            if style_variable is not None and style_combo is not None:
                style_combo.configure(values=("Sin estilo", *self.music_styles))
                style_variable.set(item.get("music_style") or "Sin estilo")
        for item, style_variable, style_combo in self.search_queue_sidebar_widgets:
            if item.get("music_style") not in self.music_styles:
                item["music_style"] = ""
            style_combo.configure(values=("Sin estilo", *self.music_styles))
            style_variable.set(item.get("music_style") or "Sin estilo")
        self._refresh_search_queue_sidebar()
        self.status.set("Ajustes guardados.")
        self._append_log("Ajustes guardados.")
        return True

    def _toggle_maximize(self) -> None:
        if self.root.state() == "zoomed":
            self.root.state("normal")
            if self._restore_geometry:
                self.root.geometry(self._restore_geometry)
            self.maximize_button.set_text("□")
        else:
            self._restore_geometry = self.root.geometry()
            self.root.state("zoomed")
            self.maximize_button.set_text("❐")

    def _close_window(self) -> None:
        if self.search_preview_window is not None:
            try:
                if self.search_preview_window.window.winfo_exists():
                    self.search_preview_window.close()
            except tk.TclError:
                pass
        self.root.destroy()
