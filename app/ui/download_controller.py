"""Coordinates metadata lookup, user actions, and download progress."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlsplit


class DownloadControllerMixin:
    """Keeps the UI responsive while coordinating the media provider."""

    def _update_clip_editor_button(self) -> None:
        if self._vlc_install_complete:
            self.clip_editor_button.command = None
            self.clip_editor_button.configure(
                text="Reinicia la app", state="disabled"
            )
            return

        if not self._vlc_available:
            self.clip_editor_button.command = self._install_vlc
            self.clip_editor_button.configure(
                text="Instalando VLC..." if self._vlc_installing else "Instalar VLC",
                state="disabled" if self._vlc_installing else "normal",
            )
            return

        self.clip_editor_button.command = self._open_clip_editor
        available = (
            self.metadata_ready
            and not self.downloading
            and not self._preview_loading
            and self.download_mode.get() == "single"
            and len(self.items) == 1
        )
        self.clip_editor_button.configure(
            state="normal" if available else "disabled"
        )
        if self.clip_section is None:
            text = "Editar fragmento"
        else:
            start, end = self.clip_section
            text = (
                f"Fragmento {self._format_time(start)}–{self._format_time(end)}"
            )
        self.clip_editor_button.configure(text=text)

    def _install_vlc(self) -> None:
        if self._vlc_installing or self._vlc_install_complete:
            return
        winget = shutil.which("winget")
        if not winget:
            if messagebox.askyesno(
                "winget no está disponible",
                "No se encontró winget en Windows. ¿Quieres abrir la página "
                "oficial para instalar VLC manualmente?",
            ):
                if not webbrowser.open("https://www.videolan.org/vlc/"):
                    messagebox.showerror(
                        "No se pudo abrir la página",
                        "Abre https://www.videolan.org/vlc/ para descargar VLC.",
                    )
            return
        if not messagebox.askyesno(
            "Instalar VLC",
            "youMP3gmr abrirá winget para instalar VLC media player de 64 bits. "
            "La instalación puede solicitar permisos de Windows. ¿Continuar?",
        ):
            return

        try:
            process = subprocess.Popen(
                [winget, "install", "--id", "VideoLAN.VLC", "--exact", "--interactive"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError as error:
            messagebox.showerror(
                "No se pudo iniciar la instalación",
                f"Windows no pudo iniciar winget.\n\n{error}",
            )
            return

        self._vlc_installing = True
        self._update_clip_editor_button()
        self.status.set("Instalando VLC. Sigue las indicaciones de la ventana de winget.")
        threading.Thread(
            target=self._wait_for_vlc_install,
            args=(process,),
            daemon=True,
        ).start()

    def _wait_for_vlc_install(self, process: subprocess.Popen[bytes]) -> None:
        self.messages.put(("vlc_install_finished", process.wait()))

    @staticmethod
    def _format_time(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _set_clip_section(self, section: tuple[float, float] | None) -> None:
        self.clip_section = section
        self._update_clip_editor_button()
        if section is None:
            self.status.set("Se descargará la canción completa.")
        else:
            self.status.set(
                f"Fragmento seleccionado: {self._format_time(section[0])}–"
                f"{self._format_time(section[1])}. Pulsa descargar."
            )

    def _open_clip_editor(self) -> None:
        if self.download_mode.get() != "single" or len(self.items) != 1:
            return
        if self.clip_editor_window is not None:
            try:
                if self.clip_editor_window.window.winfo_exists():
                    self.clip_editor_window.window.lift()
                    return
            except tk.TclError:
                self.clip_editor_window = None
        self._preview_loading = True
        self._update_clip_editor_button()
        self.status.set("Preparando vista previa del video...")
        item = self.items[0]
        threading.Thread(
            target=self._load_preview_stream,
            args=(item["url"], item["title"], item.get("duration")),
            daemon=True,
        ).start()

    def _close_clip_editor(self) -> None:
        if self.clip_editor_window is None:
            return
        try:
            if self.clip_editor_window.window.winfo_exists():
                self.clip_editor_window.close()
        except tk.TclError:
            pass
        self.clip_editor_window = None

    def _load_preview_stream(
        self,
        video_url: str,
        title: str,
        duration: float | None,
    ) -> None:
        try:
            (
                stream_url,
                http_headers,
                audio_stream_url,
                audio_http_headers,
            ) = self.media_provider.resolve_preview_stream(video_url, self.messages)
            self.messages.put(
                (
                    "preview_ready",
                    (
                        title,
                        duration,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                    ),
                )
            )
        except Exception as error:
            self.messages.put(("preview_failed", str(error)))

    def _start_download_all(self) -> None:
        for widgets in self.item_widgets:
            widgets["selected"].set(True)
        self._update_selection_count()
        self._update_clip_editor_button()
        self._start_download()

    def _start_metadata_lookup(self) -> None:
        url = self.url.get().strip()
        output_directory = Path(self.output_directory.get()).expanduser()
        if not url:
            messagebox.showerror("Falta el enlace", "Pega un enlace de video o playlist.")
            return
        if not output_directory.is_dir():
            messagebox.showerror(
                "Carpeta no válida", "Elige una carpeta de destino que exista."
            )
            return

        parsed_url = urlsplit(url)
        query = parse_qs(parsed_url.query)
        playlist_ids = query.get("list", [])
        is_mix = any(item.upper().startswith("RD") for item in playlist_ids)
        single_video = self.download_mode.get() == "single"
        is_youtube = parsed_url.hostname is not None and (
            parsed_url.hostname == "youtu.be"
            or parsed_url.hostname.endswith("youtube.com")
        )
        is_video_url = bool(query.get("v")) or (
            parsed_url.hostname == "youtu.be" and bool(parsed_url.path.strip("/"))
        )
        if is_mix and not single_video:
            messagebox.showerror(
                "Mezcla automática de YouTube",
                "Ese enlace es una mezcla automática, no una playlist fija. "
                "Selecciona «Canción individual».",
            )
            return
        if is_youtube and single_video and playlist_ids and not is_video_url:
            messagebox.showerror(
                "Falta el enlace de la canción",
                "Para el modo individual, pega el enlace directo de la canción.",
            )
            return
        if is_youtube and not single_video and not playlist_ids:
            messagebox.showerror(
                "Falta la playlist",
                "Para descargar una playlist, pega su enlace, que debe incluir "
                "el identificador de la lista.",
            )
            return

        self._set_loading(True)
        metadata_url = url
        if is_youtube and not single_video and playlist_ids:
            metadata_url = (
                "https://www.youtube.com/playlist?"
                + urlencode({"list": playlist_ids[0]})
            )

        self._reset_metadata()
        self.metadata_ready = False
        self._set_controls_enabled(False)
        self.analyze_button.configure(text="Analizando...")
        self.clip_editor_button.configure(state="disabled")
        self._set_action_text("Analizando playlist...")
        self.status.set("Obteniendo información y portadas...")
        if metadata_url != url:
            self._append_log("Abriendo la playlist directamente para cargar todos sus videos.")
        else:
            self._append_log("Consultando los metadatos del enlace.")
        threading.Thread(
            target=self._load_metadata,
            args=(metadata_url, single_video),
            daemon=True,
        ).start()

    def _load_metadata(self, url: str, single_video: bool) -> None:
        """Fetch metadata off the UI thread and publish results as queue events."""
        try:
            info = self.media_provider.extract_metadata(
                url, single_video, self.messages
            )
            if not info:
                raise ValueError("No se encontraron metadatos para este enlace.")

            entries = info.get("entries")
            if entries is None:
                entries = [info]
            items = [self.media_provider.normalize_metadata(entry) for entry in entries if entry]
            if not items:
                raise ValueError("No se encontraron videos en el enlace.")
            playlist_title = info.get("title", "Playlist")
            self.messages.put(("metadata", (items, playlist_title)))

            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {
                    executor.submit(
                        self.media_provider.fetch_thumbnail, item.get("thumbnail")
                    ): index
                    for index, item in enumerate(items)
                    if item.get("thumbnail")
                }
                for future in as_completed(futures):
                    index = futures[future]
                    try:
                        image_data = future.result()
                        if image_data:
                            self.messages.put(("thumbnail", (index, image_data)))
                    except (OSError, URLError, ValueError) as error:
                        self.messages.put(
                            ("log", f"No se pudo cargar una portada: {error}")
                        )
            self.messages.put(("metadata_complete", None))
        except Exception as error:
            self.messages.put(("metadata_failed", str(error)))

    def _start_download(self) -> None:
        selected_indices = [
            index
            for index, widgets in enumerate(self.item_widgets)
            if widgets["selected"].get()
        ]
        if not selected_indices:
            messagebox.showerror(
                "No hay canciones seleccionadas",
                "Selecciona al menos una canción de la cola.",
            )
            return
        output_directory = Path(self.output_directory.get()).expanduser()
        if not output_directory.is_dir():
            messagebox.showerror(
                "Carpeta no válida", "Elige una carpeta de destino que exista."
            )
            return
        self.downloading = True
        self._close_clip_editor()
        self._update_clip_editor_button()
        self._set_controls_enabled(False)
        self._set_action_text("Descargando...")
        self.download_count = len(selected_indices)
        self.completed_count = 0
        self.overall_progress.configure(value=0)
        self.progress_summary.configure(text=f"0 de {self.download_count} canciones")
        self.status.set(f"Descargando 0 de {self.download_count}...")
        for widgets in self.item_widgets:
            if widgets["selected"].get():
                widgets["progress"].configure(value=0)
                widgets["percentage"].configure(text="0%")
                widgets["status"].configure(text="● En cola")
        threading.Thread(
            target=self._download_items,
            args=(
                output_directory,
                self.download_mode.get() == "single",
                selected_indices,
                self.embed_metadata.get(),
                self.clip_section if self.download_mode.get() == "single" else None,
            ),
            daemon=True,
        ).start()

    def _download_items(
        self,
        output_directory: Path,
        single_video: bool,
        selected_indices: list[int] | None = None,
        embed_metadata: bool = True,
        clip_section: tuple[float, float] | None = None,
    ) -> None:
        """Download selected tracks sequentially while keeping Tk calls on its thread."""
        playlist_directory = output_directory
        if not single_video and self.items:
            folder_name = self.media_provider.sanitize_filename(
                getattr(self, "playlist_title", "Playlist")
            ) or "Playlist"
            playlist_directory = output_directory / folder_name
            try:
                playlist_directory.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                self.messages.put(("download_setup_failed", str(error)))
                return

        failed = 0
        download_indices = (
            selected_indices if selected_indices is not None else list(range(len(self.items)))
        )
        for index in download_indices:
            item = self.items[index]
            video_url = item.get("url")
            if not video_url:
                failed += 1
                self.messages.put(
                    ("item_error", (index, "No se encontró el enlace del video."))
                )
                continue
            if single_video and clip_section is not None:
                output_template = "%(title)s - fragmento.%(ext)s"
            elif single_video:
                output_template = "%(title)s.%(ext)s"
            else:
                output_template = f"{index + 1:03d} - %(title)s.%(ext)s"
            progress_hook = (
                lambda data, item_index=index: self._download_progress(item_index, data)
            )
            self.messages.put(("item_status", (index, "Preparando...")))
            try:
                output_path = self.media_provider.download_audio(
                    video_url,
                    playlist_directory / output_template,
                    progress_hook,
                    self.messages,
                    embed_metadata,
                    clip_section if single_video else None,
                )
                self.messages.put(("item_done", (index, output_path)))
            except Exception as error:
                failed += 1
                self.messages.put(("item_error", (index, str(error))))
        self.messages.put(("download_complete", (failed, len(download_indices))))

    def _download_progress(self, index: int, data: dict[str, Any]) -> None:
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if total:
                percent = data.get("downloaded_bytes", 0) * 100 / total
                self.messages.put(("progress", (index, percent)))
                self.messages.put(
                    ("item_status", (index, f"Descargando... {percent:.1f}%"))
                )
                speed = data.get("speed")
                if speed:
                    self.messages.put(("item_speed", (index, self._format_speed(speed))))
        elif data.get("status") == "finished":
            self.messages.put(("progress", (index, 100)))
            self.messages.put(("item_status", (index, "Convirtiendo a MP3...")))

    def _process_messages(self) -> None:
        """Apply worker events to widgets on Tk's main event loop."""
        try:
            while True:
                event, value = self.messages.get_nowait()
                if event == "log":
                    self._append_log(str(value))
                elif event == "preview_ready":
                    (
                        title,
                        duration,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                    ) = value
                    self._preview_loading = False
                    try:
                        from app.ui.clip_editor import ClipEditorWindow

                        self.clip_editor_window = ClipEditorWindow(
                            self.root,
                            title,
                            duration,
                            stream_url,
                            http_headers,
                            audio_stream_url,
                            audio_http_headers,
                            self.palette,
                            self._set_clip_section,
                        )
                    except RuntimeError as error:
                        self.clip_editor_window = None
                        self._append_log(f"Vista previa no disponible: {error}")
                        messagebox.showerror("Vista previa no disponible", str(error))
                    self._update_clip_editor_button()
                elif event == "preview_failed":
                    self._preview_loading = False
                    self._update_clip_editor_button()
                    self._append_log(f"No se pudo abrir la vista previa: {value}")
                    messagebox.showerror(
                        "No se pudo abrir el video",
                        f"No se pudo preparar la vista previa.\n\n{value}",
                    )
                elif event == "vlc_install_finished":
                    self._vlc_installing = False
                    if value == 0:
                        self._vlc_install_complete = True
                        self.status.set(
                            "VLC se instaló. Cierra y vuelve a abrir youMP3gmr."
                        )
                        messagebox.showinfo(
                            "Instalación terminada",
                            "VLC se instaló correctamente. Cierra y vuelve a abrir "
                            "youMP3gmr para habilitar la vista previa.",
                        )
                    else:
                        self.status.set("No se pudo completar la instalación de VLC.")
                        self._append_log(
                            f"winget terminó la instalación de VLC con código {value}."
                        )
                        messagebox.showerror(
                            "Error al instalar VLC",
                            "winget no pudo completar la instalación "
                            f"(código {value}). Revisa la ventana de winget e "
                            "inténtalo de nuevo.",
                        )
                    self._update_clip_editor_button()
                elif event == "metadata":
                    items, playlist_title = value
                    self.playlist_title = playlist_title
                    self._show_items(items)
                    self.overall_progress.configure(value=0)
                    self.progress_summary.configure(text=f"0 de {len(items)} canciones")
                    self.playlist_title_label.configure(text=playlist_title)
                    self.playlist_badge.configure(text="PLAYLIST DETECTADA" if len(items) > 1 else "CANCIÓN DETECTADA")
                    self.playlist_stats.configure(
                        text=f"{len(items)} canciones · MP3 · 192 kbps"
                    )
                    noun = "pista" if len(items) == 1 else "pistas"
                    self._set_action_text(f"Descargar todo en MP3 ({len(items)} {noun})")
                    self.download_all_button.configure(state="disabled")
                    self.bottom_action_button.configure(state="disabled")
                    self.status.set(
                        f"{len(items)} video(s) encontrados. Cargando portadas..."
                    )
                elif event == "metadata_complete":
                    self.metadata_ready = True
                    self._set_loading(False)
                    self._set_controls_enabled(True)
                    self.analyze_button.configure(text="Analizar playlist")
                    self._set_action_text(
                        f"Descargar todo en MP3 ({len(self.items)} "
                        f"{'pista' if len(self.items) == 1 else 'pistas'})"
                    )
                    self.status.set(
                        f"{len(self.items)} video(s) encontrados. "
                        "Revisa la lista y descarga."
                    )
                    self._update_selection_count()
                elif event == "thumbnail":
                    index, image_data = value
                    self._set_thumbnail(index, image_data)
                    if index == 0:
                        self._set_playlist_cover(image_data)
                elif event == "metadata_failed":
                    self._set_loading(False)
                    self._set_controls_enabled(True)
                    self.analyze_button.configure(text="Analizar playlist")
                    self.download_all_button.configure(state="disabled")
                    self.bottom_action_button.configure(state="disabled")
                    self._set_action_text("Descargar todo en MP3")
                    self.status.set("No se pudo obtener la información.")
                    self._append_log(f"Error de metadatos: {value}")
                    messagebox.showerror(
                        "Error al obtener información",
                        f"No se pudieron cargar los metadatos.\n\n{value}",
                    )
                elif event == "progress":
                    index, percent = value
                    percent = min(float(percent), 100)
                    self.item_widgets[index]["progress"].configure(value=percent)
                    self.item_widgets[index]["percentage"].configure(text=f"{percent:.0f}%")
                elif event == "item_status":
                    index, text = value
                    self.item_widgets[index]["status"].configure(text=text)
                    self.status.set(
                        f"Descargando {self.completed_count + 1} de {self.download_count}: "
                        f"{self.items[index]['title']}"
                    )
                elif event == "item_done":
                    index, output_path = value
                    self.item_widgets[index]["progress"].configure(value=100)
                    self.item_widgets[index]["percentage"].configure(text="100%")
                    self.item_widgets[index]["status"].configure(
                        text="✓ Completado", style="CompleteStatus.TLabel"
                    )
                    self.item_widgets[index]["speed"].configure(text="Listo\nMP3")
                    if output_path:
                        self.item_widgets[index]["output_path"] = str(output_path)
                        self.item_widgets[index]["show_location"].configure(
                            state="normal"
                        )
                    self.completed_count += 1
                    self.overall_progress.configure(
                        value=self.completed_count * 100 / self.download_count
                    )
                    self.progress_summary.configure(
                        text=f"{self.completed_count} de {self.download_count} canciones"
                    )
                elif event == "item_error":
                    index, error = value
                    self.item_widgets[index]["status"].configure(
                        text="× Error", style="QueueStatus.TLabel"
                    )
                    self.item_widgets[index]["speed"].configure(text="Error\nSin MP3")
                    self.completed_count += 1
                    self.overall_progress.configure(
                        value=self.completed_count * 100 / self.download_count
                    )
                    self._append_log(f"Video {index + 1}: {error}")
                elif event == "item_speed":
                    index, speed = value
                    self.item_widgets[index]["speed"].configure(text=f"{speed}\nDescargando")
                elif event == "download_complete":
                    failed, total = value
                    self.downloading = False
                    self._set_controls_enabled(True)
                    self._update_clip_editor_button()
                    self._set_action_text(f"Descargar selección ({total} pistas MP3)")
                    completed = total - failed
                    self.status.set(
                        f"Descarga terminada: {completed} correcto(s), "
                        f"{failed} con error."
                    )
                    self.progress_summary.configure(text=f"{completed} de {total} canciones")
                    if failed:
                        self._append_log(
                            f"Finalizó la descarga con {failed} error(es)."
                        )
                    else:
                        self._append_log("Todos los audios se descargaron correctamente.")
                elif event == "download_setup_failed":
                    self.downloading = False
                    self._set_controls_enabled(True)
                    self._set_action_text("Descargar todo en MP3")
                    self.status.set("No se pudo crear la carpeta de destino.")
                    self._append_log(f"Error de carpeta: {value}")
                    messagebox.showerror(
                        "Error de carpeta",
                        f"No se pudo preparar la carpeta de la playlist.\n\n{value}",
                    )
        except queue.Empty:
            pass
        self.root.after(100, self._process_messages)
