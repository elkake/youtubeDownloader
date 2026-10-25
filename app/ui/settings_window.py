"""Preferences window for playback defaults and download location."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from app.services.media_provider import PREVIEW_RESOLUTIONS
from app.config.settings import validate_music_styles


class SettingsWindow:
    """Edit user preferences and save them through the application callback."""

    def __init__(
        self,
        parent: tk.Tk,
        output_directory: str,
        preview_resolution: str,
        preview_volume: int,
        concurrent_downloads: int,
        music_styles: list[str],
        on_save: Callable[[str, str, int, int, list[str]], bool],
    ) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title("Ajustes")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.on_save = on_save
        self.output_directory = tk.StringVar(value=output_directory)
        self.preview_resolution = tk.StringVar(value=preview_resolution)
        self.preview_volume = tk.DoubleVar(value=preview_volume)
        self.concurrent_downloads = tk.StringVar(value=str(concurrent_downloads))
        self.music_styles = music_styles.copy()

        content = ttk.Frame(self.window, padding=16)
        content.grid(sticky="nsew")
        content.columnconfigure(1, weight=1)
        ttk.Label(
            content,
            text="Resolución predeterminada",
            style="Panel.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 10))
        self.resolution_combo = ttk.Combobox(
            content,
            textvariable=self.preview_resolution,
            values=PREVIEW_RESOLUTIONS,
            state="readonly",
            width=16,
        )
        self.resolution_combo.grid(row=0, column=1, sticky="w", pady=(0, 10))

        ttk.Label(
            content,
            text="Volumen inicial",
            style="Panel.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=(0, 10))
        volume_controls = ttk.Frame(content)
        volume_controls.grid(row=1, column=1, sticky="ew", pady=(0, 10))
        volume_controls.columnconfigure(0, weight=1)
        self.volume_scale = ttk.Scale(
            volume_controls,
            from_=0,
            to=100,
            variable=self.preview_volume,
            command=self._update_volume_label,
        )
        self.volume_scale.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.volume_label = ttk.Label(
            volume_controls,
            text=f"{preview_volume}%",
            style="PanelMuted.TLabel",
            width=5,
            anchor="e",
        )
        self.volume_label.grid(row=0, column=1)

        ttk.Label(
            content,
            text="Descargas simultáneas",
            style="Panel.TLabel",
        ).grid(row=2, column=0, sticky="w", padx=(0, 12), pady=(0, 10))
        concurrency_controls = ttk.Frame(content)
        concurrency_controls.grid(row=2, column=1, sticky="w", pady=(0, 10))
        self.concurrency_spinbox = ttk.Spinbox(
            concurrency_controls,
            from_=2,
            to=16,
            increment=1,
            textvariable=self.concurrent_downloads,
            width=5,
            state="normal",
        )
        self.concurrency_spinbox.pack(side="left", padx=(0, 8))
        ttk.Label(
            concurrency_controls,
            text="(de 2 a 16)",
            style="PanelMuted.TLabel",
        ).pack(side="left")

        ttk.Label(
            content,
            text="Carpeta de descarga",
            style="Panel.TLabel",
        ).grid(row=4, column=0, sticky="nw", padx=(0, 12))
        folder_controls = ttk.Frame(content)
        folder_controls.grid(row=4, column=1, sticky="ew")
        folder_controls.columnconfigure(0, weight=1)
        self.folder_entry = ttk.Entry(
            folder_controls,
            textvariable=self.output_directory,
            width=46,
        )
        self.folder_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(
            folder_controls,
            text="Elegir...",
            command=self._choose_folder,
        ).grid(row=0, column=1)

        ttk.Label(
            content,
            text="Estilos musicales",
            style="Panel.TLabel",
        ).grid(row=3, column=0, sticky="nw", padx=(0, 12), pady=(0, 10))
        style_controls = ttk.Frame(content)
        style_controls.grid(row=3, column=1, sticky="ew", pady=(0, 10))
        style_controls.columnconfigure(0, weight=1)
        self.style_listbox = tk.Listbox(
            style_controls,
            height=5,
            exportselection=False,
            selectmode="browse",
        )
        self.style_listbox.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        style_buttons = ttk.Frame(style_controls)
        style_buttons.grid(row=0, column=1, sticky="n")
        self.style_entry = ttk.Entry(style_buttons, width=18)
        self.style_entry.pack(fill="x", pady=(0, 5))
        ttk.Button(
            style_buttons,
            text="Agregar estilo",
            command=self._add_music_style,
        ).pack(fill="x", pady=(0, 5))
        ttk.Button(
            style_buttons,
            text="Quitar seleccionado",
            command=self._remove_music_style,
        ).pack(fill="x")
        self._refresh_music_styles()

        actions = ttk.Frame(content)
        actions.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(actions, text="Cancelar", command=self.close).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            actions,
            text="Guardar",
            command=self._save,
            style="Primary.TButton",
        ).pack(side="right")
        self.window.grab_set()

    def _update_volume_label(self, value: str) -> None:
        self.volume_label.configure(text=f"{round(float(value))}%")

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(
            parent=self.window,
            initialdir=self.output_directory.get(),
            title="Elegir carpeta de descarga",
        )
        if folder:
            self.output_directory.set(folder)

    def _refresh_music_styles(self) -> None:
        self.style_listbox.delete(0, "end")
        for style in self.music_styles:
            self.style_listbox.insert("end", style)

    def _add_music_style(self) -> None:
        candidate = self.style_entry.get().strip()
        if not candidate:
            return
        try:
            styles = validate_music_styles([*self.music_styles, candidate])
        except ValueError as error:
            messagebox.showerror(
                "Estilo no válido",
                str(error),
                parent=self.window,
            )
            return
        self.music_styles = styles
        self.style_entry.delete(0, "end")
        self._refresh_music_styles()

    def _remove_music_style(self) -> None:
        selection = self.style_listbox.curselection()
        if not selection:
            return
        del self.music_styles[selection[0]]
        self._refresh_music_styles()

    def _save(self) -> None:
        folder = self.output_directory.get().strip()
        if not Path(folder).expanduser().is_dir():
            messagebox.showerror(
                "Carpeta no válida",
                "Elige una carpeta de descarga que exista.",
                parent=self.window,
            )
            return
        try:
            concurrent_downloads = int(self.concurrent_downloads.get())
        except ValueError:
            messagebox.showerror(
                "Cantidad no válida",
                "Escribe un número entero de descargas simultáneas entre 2 y 16.",
                parent=self.window,
            )
            return
        if not 2 <= concurrent_downloads <= 16:
            messagebox.showerror(
                "Cantidad no válida",
                "El número de descargas simultáneas debe estar entre 2 y 16.",
                parent=self.window,
            )
            return
        if self.on_save(
            folder,
            self.preview_resolution.get(),
            round(self.preview_volume.get()),
            concurrent_downloads,
            self.music_styles.copy(),
        ):
            self.close()

    def close(self) -> None:
        if self.window.winfo_exists():
            self.window.grab_release()
            self.window.destroy()
