"""Coordinates metadata lookup, user actions, and download progress."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog
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

    def _open_search_preview(self, index: int) -> None:
        if (
            self.download_mode.get() != "search"
            or self._search_view != "results"
            or not 0 <= index < len(self.search_results)
        ):
            return
        if self.search_preview_window is not None:
            try:
                if self.search_preview_window.window.winfo_exists():
                    self.search_preview_window.window.lift()
                    return
            except tk.TclError:
                self.search_preview_window = None
        if self._search_preview_loading:
            return
        if not self._vlc_available:
            messagebox.showerror(
                "Vista previa no disponible",
                "Para reproducir videos instala VLC media player de 64 bits "
                "con el botón «Instalar VLC» del modo Canción.",
            )
            return
        item = self.search_results[index]
        self._search_preview_generation += 1
        generation = self._search_preview_generation
        self._search_preview_loading = True
        resolution = self.preview_resolution.get()
        self.item_widgets[index]["play_button"].configure(state="disabled")
        self.status.set(f"Preparando vista previa: {item['title']}")
        threading.Thread(
            target=self._load_search_preview_stream,
            args=(
                item["url"],
                item["title"],
                item.get("duration"),
                index,
                generation,
                resolution,
                self.preview_volume,
            ),
            daemon=True,
        ).start()

    def _load_search_preview_stream(
        self,
        video_url: str,
        title: str,
        duration: float | None,
        index: int,
        generation: int,
        resolution: str,
        volume: int,
    ) -> None:
        try:
            max_height = self._preview_max_height(resolution)
            (
                stream_url,
                http_headers,
                audio_stream_url,
                audio_http_headers,
            ) = self.media_provider.resolve_preview_stream(
                video_url,
                self.messages,
                max_height,
                prefer_lowest=resolution == "Más baja",
            )
            self.messages.put(
                (
                    "search_preview_ready",
                    (
                        generation,
                        index,
                        title,
                        duration,
                        video_url,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                        resolution,
                        volume,
                    ),
                )
            )
        except Exception as error:
            self.messages.put(
                ("search_preview_failed", (generation, index, str(error)))
            )

    def _wait_for_vlc_install(self, process: subprocess.Popen[bytes]) -> None:
        self.messages.put(("vlc_install_finished", process.wait()))

    def _on_mode_changed(self) -> None:
        if self.downloading:
            return
        self._search_view = "results"
        self._search_query = ""
        self._search_preview_generation += 1
        self._search_preview_loading = False
        self._reset_metadata()
        if self.download_mode.get() == "search":
            self.paste_button.grid_remove()
            self.search_page.place(
                x=0,
                y=38,
                relwidth=1,
                relheight=1,
                height=-38,
            )
            self.search_page.lift()
            self.search_results_heading.configure(
                text="Busca canciones, artistas o videos"
            )
            self.status.set("Escribe qué quieres escuchar y pulsa «Buscar videos».")
        else:
            self.paste_button.grid()
            self.search_page.place_forget()
        self.analyze_button.configure(
            text="Buscar videos" if self.download_mode.get() == "search"
            else "Analizar playlist"
        )
        self._update_search_queue_button()

    def _select_download_mode(self, mode: str) -> None:
        if self.downloading:
            return
        self.download_mode.set(mode)
        self._on_mode_changed()

    def _start_search_from_page(self) -> None:
        query = self.search_query.get().strip()
        if not query:
            self.search_entry.focus_set()
            messagebox.showerror(
                "Falta la búsqueda",
                "Escribe una canción, artista o video para buscar.",
            )
            return
        self._start_youtube_search(query)

    def _update_search_queue_button(self) -> None:
        if self.download_mode.get() != "search":
            self.search_queue_button.pack_forget()
            self.search_queue_clear_button.pack_forget()
            return
        text = (
            f"Volver a resultados ({len(self.search_results)})"
            if self._search_view == "queue"
            else f"Ver cola ({len(self.search_queue)})"
        )
        self.search_queue_button.configure(
            text=text,
            state="disabled" if self.downloading or self._loading else "normal",
        )
        self.search_queue_page_button.configure(
            text=f"Ver cola ({len(self.search_queue)})",
            state="disabled" if self.downloading or self._loading else "normal",
        )
        if hasattr(self, "search_queue_download_button"):
            enabled = bool(self.search_queue) and not self.downloading and not self._loading
            self.search_queue_download_button.configure(
                state="normal" if enabled else "disabled"
            )
            self.search_queue_sidebar_clear_button.configure(
                state="normal" if enabled else "disabled"
            )
        self.search_queue_button.pack(fill="x", pady=(0, 5), ipady=2)
        if self._search_view == "queue" and self.search_queue:
            self.search_queue_clear_button.configure(
                state="disabled" if self.downloading or self._loading else "normal"
            )
            self.search_queue_clear_button.pack(fill="x", pady=(0, 5), ipady=2)
        else:
            self.search_queue_clear_button.pack_forget()

    def _toggle_search_queue_view(self) -> None:
        if self.download_mode.get() != "search" or self.downloading:
            return
        if self._search_view == "results":
            self.search_results = self.items
            self._search_view = "queue"
            self.search_page.place_forget()
            self._show_items(self.search_queue)
            self.metadata_ready = bool(self.search_queue)
            self.playlist_badge.configure(text="COLA DE DESCARGA")
            self.playlist_title_label.configure(text="Videos añadidos")
            self.playlist_stats.configure(
                text=f"{len(self.search_queue)} videos en la cola"
            )
            self.status.set(
                "Selecciona videos y pulsa descargar cuando quieras."
                if self.search_queue
                else "La cola está vacía. Busca videos y añádelos."
            )
        else:
            self._search_view = "results"
            self._show_items(self.search_results)
            self.search_page.place(
                x=0,
                y=38,
                relwidth=1,
                relheight=1,
                height=-38,
            )
            self.search_page.lift()
            self.metadata_ready = bool(self.search_results)
            self.search_results_heading.configure(
                text=f"Resultados para «{self._search_query}»"
            )
            self.playlist_badge.configure(text="RESULTADOS DE BÚSQUEDA")
            self.playlist_title_label.configure(
                text=f"Resultados: {self._search_query}"
            )
            self.playlist_stats.configure(
                text=f"{len(self.search_results)} videos encontrados"
            )
            self.status.set("Añade los videos que quieras a la cola de descarga.")
        self._set_controls_enabled(True)
        if self._search_view == "results":
            self.select_all_checkbox.configure(state="disabled")
            for widgets in self.item_widgets:
                widgets["checkbox"].configure(state="disabled")
            self.download_all_button.configure(state="disabled")
            self.bottom_action_button.configure(state="disabled")
        elif not self.search_queue:
            self.download_all_button.configure(state="disabled")
            self.bottom_action_button.configure(state="disabled")
        self._update_selection_count()
        if self._search_view == "results":
            self._set_action_text("Añade videos a la cola para descargarlos")
        self._update_search_queue_button()

    def _add_search_result(self, index: int) -> None:
        if self._search_view != "results" or not 0 <= index < len(self.items):
            return
        item = self.items[index]
        video_url = item.get("url")
        if not video_url:
            messagebox.showerror(
                "Video no disponible",
                "No se encontró el enlace para añadir este resultado.",
            )
            return
        if any(queued.get("url") == video_url for queued in self.search_queue):
            return
        self.search_queue.append(item)
        self.item_widgets[index]["add_button"].configure(
            state="disabled"
        )
        self._refresh_search_queue_sidebar()
        self._update_search_queue_button()
        self.status.set(f"Agregado a la cola: {item['title']}")
        self._append_log(f"Agregado a la cola: {item['title']}")

    def _remove_search_queue_item(self, index: int) -> None:
        if self._search_view != "queue" or not 0 <= index < len(self.search_queue):
            return
        removed = self.search_queue.pop(index)
        self._show_items(self.search_queue)
        self._refresh_search_queue_sidebar()
        self.metadata_ready = bool(self.search_queue)
        self.playlist_stats.configure(
            text=f"{len(self.search_queue)} videos en la cola"
        )
        self.status.set(f"Quitado de la cola: {removed['title']}")
        if not self.search_queue:
            self.download_all_button.configure(state="disabled")
            self.bottom_action_button.configure(state="disabled")
        self._update_search_queue_button()

    def _clear_search_queue(self) -> None:
        if self.download_mode.get() != "search" or self.downloading or not self.search_queue:
            return
        self.search_queue.clear()
        self._refresh_search_queue_sidebar()
        if self._search_view == "queue":
            self._show_items([])
            self.metadata_ready = False
            self.playlist_stats.configure(text="0 videos en la cola")
            self.status.set("La cola está vacía. Busca videos y añádelos.")
            self.download_all_button.configure(state="disabled")
            self.bottom_action_button.configure(state="disabled")
            self._set_action_text("Añade videos a la cola para descargarlos")
        else:
            for index, item in enumerate(self.search_results):
                if index < len(self.item_widgets):
                    self.item_widgets[index]["add_button"].configure(
                        state="disabled" if self.downloading or self._loading else "normal"
                    )
            self.status.set("Se vació la lista de videos.")
        self._append_log("Se vació la cola de búsqueda.")
        self._update_search_queue_button()

    def _remove_search_queue_sidebar_item(self, index: int) -> None:
        if self.download_mode.get() != "search" or not 0 <= index < len(self.search_queue):
            return
        removed = self.search_queue.pop(index)
        self._refresh_search_queue_sidebar()
        self._update_search_queue_button()
        self.status.set(f"Quitado de la lista: {removed['title']}")
        if self._search_view == "queue":
            self._show_items(self.search_queue)
            self.metadata_ready = bool(self.search_queue)
            self.playlist_stats.configure(
                text=f"{len(self.search_queue)} videos en la cola"
            )
            if not self.search_queue:
                self.download_all_button.configure(state="disabled")
                self.bottom_action_button.configure(state="disabled")
        else:
            for item_index, item in enumerate(self.search_results):
                if item.get("url") == removed.get("url"):
                    self.item_widgets[item_index]["add_button"].configure(
                        state="normal",
                    )
                    break

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
            args=(
                item["url"],
                item["title"],
                item.get("duration"),
                self.preview_resolution.get(),
                self.preview_volume,
            ),
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
        resolution: str,
        volume: int,
    ) -> None:
        try:
            max_height = self._preview_max_height(resolution)
            (
                stream_url,
                http_headers,
                audio_stream_url,
                audio_http_headers,
            ) = self.media_provider.resolve_preview_stream(
                video_url,
                self.messages,
                max_height,
                prefer_lowest=resolution == "Más baja",
            )
            self.messages.put(
                (
                    "preview_ready",
                    (
                        title,
                        duration,
                        video_url,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                        resolution,
                        volume,
                    ),
                )
            )
        except Exception as error:
            self.messages.put(("preview_failed", str(error)))

    @staticmethod
    def _preview_max_height(resolution: str) -> int | None:
        if resolution in {"Automática", "Más baja"}:
            return None
        try:
            return int(resolution.removesuffix("p"))
        except ValueError as error:
            raise ValueError(f"Resolución no válida: {resolution}") from error

    def _request_preview_quality(
        self,
        target_window: Any,
        resolution: str,
    ) -> None:
        if resolution in {"Automática", "Más baja"}:
            max_height = None
        else:
            try:
                max_height = int(resolution.removesuffix("p"))
            except ValueError as error:
                raise ValueError(f"Resolución no válida: {resolution}") from error
        threading.Thread(
            target=self._load_preview_quality_stream,
            args=(
                target_window,
                target_window.video_url,
                resolution,
                max_height,
            ),
            daemon=True,
        ).start()

    def _load_preview_quality_stream(
        self,
        target_window: Any,
        video_url: str,
        resolution: str,
        max_height: int | None,
    ) -> None:
        try:
            (
                stream_url,
                http_headers,
                audio_stream_url,
                audio_http_headers,
            ) = self.media_provider.resolve_preview_stream(
                video_url,
                self.messages,
                max_height,
                prefer_lowest=resolution == "Más baja",
            )
            self.messages.put(
                (
                    "preview_quality_ready",
                    (
                        target_window,
                        resolution,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                    ),
                )
            )
        except Exception as error:
            self.messages.put(
                ("preview_quality_failed", (target_window, str(error)))
            )

    def _start_download_all(self) -> None:
        if self.download_mode.get() == "search" and self._search_view != "queue":
            self._start_download()
            return
        for widgets in self.item_widgets:
            widgets["selected"].set(True)
        self._update_selection_count()
        self._update_clip_editor_button()
        self._start_download()

    def _start_metadata_lookup(self) -> None:
        url = self.url.get().strip()
        if self.download_mode.get() == "search":
            self._start_youtube_search(url)
            return
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

    def _start_youtube_search(self, query: str) -> None:
        if not query:
            messagebox.showerror("Falta la búsqueda", "Escribe qué video quieres buscar.")
            return
        self._search_generation += 1
        generation = self._search_generation
        self._search_view = "results"
        self._reset_metadata()
        self._search_query = query
        self._set_loading(True)
        self._set_search_loading(True)
        self.metadata_ready = False
        self._set_controls_enabled(False)
        self.analyze_button.configure(text="Buscando...")
        self.search_results_heading.configure(text=f"Buscando «{query}»...")
        self._update_search_queue_button()
        self.status.set("Buscando videos en YouTube...")
        self._append_log(f"Buscando en YouTube: {query}")
        threading.Thread(
            target=self._load_search_results,
            args=(query, generation),
            daemon=True,
        ).start()

    def _load_search_results(self, query: str, generation: int) -> None:
        try:
            info = self.media_provider.search_videos(
                query,
                self.messages,
                limit=30,
            )
            entries = (info or {}).get("entries") or []
            items = [
                self.media_provider.normalize_metadata(entry)
                for entry in entries
                if entry
            ]
            if not items:
                self.messages.put(("search_failed", (generation, "No se encontraron videos. Prueba con otros términos.")))
                return
            self.messages.put(("search_results", (items, query, generation)))
            self.messages.put(("metadata_complete", ("search", generation)))
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
                            self.messages.put(
                                ("search_thumbnail", (generation, index, image_data))
                            )
                    except (OSError, URLError, ValueError) as error:
                        self.messages.put(
                            ("log", f"No se pudo cargar una portada: {error}")
                        )
        except Exception as error:
            self.messages.put(("search_failed", (generation, str(error))))

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
        if (
            self.download_mode.get() == "search"
            and self._search_view != "queue"
        ):
            messagebox.showinfo(
                "Abre la cola de descarga",
                "Primero añade videos y pulsa «Ver cola» para descargarlos.",
            )
            return
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
        audio_language = None
        if self.download_mode.get() == "single" and len(selected_indices) == 1:
            tracks = self.items[selected_indices[0]].get("audio_tracks") or []
            if len(tracks) > 1:
                choices = "\n".join(
                    f"{index + 1}. {track['label']} ({track['language']})"
                    for index, track in enumerate(tracks)
                )
                selected_track = simpledialog.askinteger(
                    "Elegir pista de audio",
                    "Este video tiene varias pistas de audio. Escribe el número "
                    f"del idioma que quieres descargar:\n\n{choices}",
                    parent=self.root,
                    minvalue=1,
                    maxvalue=len(tracks),
                )
                if selected_track is None:
                    return
                audio_language = tracks[selected_track - 1]["language"]
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
                self.download_mode.get() != "playlist",
                selected_indices,
                self.embed_metadata.get(),
                self.clip_section if self.download_mode.get() == "single" else None,
                self.concurrent_downloads,
                self.download_mode.get() == "playlist",
                self.music_styles.copy(),
                audio_language,
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
        max_workers: int = 2,
        playlist_mode: bool = False,
        music_styles: list[str] | None = None,
        audio_language: str | None = None,
    ) -> None:
        """Download selected tracks concurrently and publish worker events."""
        playlist_name: str | None = None
        if playlist_mode and self.items:
            playlist_name = self.media_provider.sanitize_filename(
                getattr(self, "playlist_title", "Playlist")
            ) or "Playlist"

        failed = 0
        failures: list[tuple[int, str, str, Path]] = []
        allowed_styles = set(music_styles or [])
        download_indices = (
            selected_indices if selected_indices is not None else list(range(len(self.items)))
        )

        def download_one(index: int) -> tuple[int, str, str, Path] | None:
            item = self.items[index]
            video_url = item.get("url")
            destination_directory = output_directory
            try:
                music_style = item.get("music_style") or ""
                if music_style and music_style not in allowed_styles:
                    raise ValueError(f"El estilo musical ya no está disponible: {music_style}")
                destination_directory = (
                    output_directory / music_style if music_style else output_directory
                )
                if playlist_name:
                    destination_directory /= playlist_name
                destination_directory.mkdir(parents=True, exist_ok=True)
                if not video_url:
                    error_message = "No se encontró el enlace del video."
                    self.messages.put(("item_error", (index, error_message)))
                    return (
                        index,
                        "URL no disponible",
                        error_message,
                        destination_directory,
                    )
                if single_video and clip_section is not None:
                    output_template = "%(title)s - fragmento.%(ext)s"
                elif single_video and len(download_indices) == 1:
                    output_template = "%(title)s.%(ext)s"
                else:
                    output_template = f"{index + 1:03d} - %(title)s.%(ext)s"
                progress_hook = (
                    lambda data, item_index=index: self._download_progress(
                        item_index, data
                    )
                )
                self.messages.put(("item_status", (index, "Preparando...")))
                output_path = self.media_provider.download_audio(
                    video_url,
                    destination_directory / output_template,
                    progress_hook,
                    self.messages,
                    embed_metadata,
                    clip_section if single_video else None,
                    audio_language if single_video else None,
                )
                self.messages.put(("item_done", (index, output_path)))
            except Exception as error:
                self.messages.put(("item_error", (index, str(error))))
                return (
                    index,
                    str(video_url or "URL no disponible"),
                    str(error),
                    destination_directory,
                )
            return None

        if download_indices:
            worker_count = min(max(2, min(max_workers, 16)), len(download_indices))
            try:
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures = [
                        executor.submit(download_one, index)
                        for index in download_indices
                    ]
                    for future in as_completed(futures):
                        failure = future.result()
                        if failure:
                            failures.append(failure)
                            failed += 1
            except Exception as error:
                self.messages.put(("download_setup_failed", str(error)))
                return
        if failures and playlist_mode:
            failure_logs: dict[Path, list[tuple[int, str, str]]] = {}
            for index, failed_url, error, folder in failures:
                failure_logs.setdefault(folder, []).append((index, failed_url, error))
            for folder, folder_failures in failure_logs.items():
                failure_log = folder / f"fallas_{date.today().isoformat()}.txt"
                try:
                    with failure_log.open(
                        "a", encoding="utf-8", newline="\n"
                    ) as log_file:
                        for _, failed_url, error in sorted(folder_failures):
                            log_file.write(f"URL: {failed_url}\nError: {error}\n\n")
                except OSError as error:
                    self.messages.put(("failure_log_failed", str(error)))
                else:
                    self.messages.put(("failure_log_written", str(failure_log)))
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
                        video_url,
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
                            video_url,
                            self._request_preview_quality,
                            resolution,
                            volume,
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
                elif event == "preview_quality_ready":
                    (
                        target_window,
                        resolution,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                    ) = value
                    target_window.set_resolution_stream(
                        resolution,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                    )
                elif event == "preview_quality_failed":
                    target_window, error = value
                    target_window.resolution_change_failed(str(error))
                elif event == "search_preview_ready":
                    (
                        generation,
                        index,
                        title,
                        duration,
                        video_url,
                        stream_url,
                        http_headers,
                        audio_stream_url,
                        audio_http_headers,
                        resolution,
                        volume,
                    ) = value
                    if generation != self._search_preview_generation:
                        continue
                    self._search_preview_loading = False
                    try:
                        from app.ui.clip_editor import SearchPreviewWindow

                        self.search_preview_window = SearchPreviewWindow(
                            self.root,
                            title,
                            duration,
                            stream_url,
                            http_headers,
                            audio_stream_url,
                            audio_http_headers,
                            self.palette,
                            video_url,
                            self._request_preview_quality,
                            resolution,
                            volume,
                        )
                    except RuntimeError as error:
                        self.search_preview_window = None
                        self._append_log(
                            f"No se pudo abrir la vista previa: {error}"
                        )
                        messagebox.showerror(
                            "Vista previa no disponible",
                            str(error),
                        )
                    finally:
                        if index < len(self.item_widgets):
                            self.item_widgets[index]["play_button"].configure(
                                state="normal"
                            )
                elif event == "search_preview_failed":
                    generation, index, error = value
                    if generation != self._search_preview_generation:
                        continue
                    self._search_preview_loading = False
                    if index < len(self.item_widgets):
                        self.item_widgets[index]["play_button"].configure(
                            state="normal"
                        )
                    self._append_log(
                        f"No se pudo preparar la vista previa: {error}"
                    )
                    messagebox.showerror(
                        "No se pudo abrir el video",
                        f"No se pudo preparar la vista previa.\n\n{error}",
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
                elif event == "search_results":
                    items, query, generation = value
                    if generation != self._search_generation:
                        continue
                    self.search_results = items
                    self.items = items
                    self._search_query = query
                    self._search_view = "results"
                    self._show_items(items)
                    self.search_page.lift()
                    self.search_results_heading.configure(
                        text=f"Resultados para «{query}» · {len(items)} videos"
                    )
                    self.playlist_badge.configure(text="RESULTADOS DE BÚSQUEDA")
                    self.playlist_title_label.configure(text=f"Resultados: {query}")
                    self.playlist_stats.configure(
                        text=f"{len(items)} videos encontrados · Máximo 30 resultados"
                    )
                    self._set_action_text("Añade videos a la cola para descargarlos")
                    self.status.set(
                        f"{len(items)} resultados. Pulsa + para añadir o ▶ para reproducir."
                    )
                elif event == "metadata_complete":
                    if (
                        isinstance(value, tuple)
                        and len(value) == 2
                        and value[0] == "search"
                        and value[1] != self._search_generation
                    ):
                        continue
                    self.metadata_ready = True
                    self._set_loading(False)
                    if (
                        isinstance(value, tuple)
                        and len(value) == 2
                        and value[0] == "search"
                    ):
                        self._set_search_loading(False)
                    self._set_controls_enabled(True)
                    self.analyze_button.configure(
                        text="Buscar videos"
                        if self.download_mode.get() == "search"
                        else "Analizar playlist"
                    )
                    if (
                        self.download_mode.get() == "search"
                        and self._search_view == "results"
                    ):
                        self.select_all_checkbox.configure(state="disabled")
                        for widgets in self.item_widgets:
                            widgets["checkbox"].configure(state="disabled")
                        self.download_all_button.configure(state="disabled")
                        self.bottom_action_button.configure(state="disabled")
                        self.status.set(
                            f"{len(self.search_results)} resultados. Pulsa + para "
                            "añadir o ▶ para reproducir."
                        )
                        self._update_search_queue_button()
                        continue
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
                elif event == "search_thumbnail":
                    generation, index, image_data = value
                    if generation == self._search_generation:
                        self._set_thumbnail(index, image_data)
                elif event == "search_failed":
                    generation, error = value
                    if generation != self._search_generation:
                        continue
                    self._set_loading(False)
                    self._set_search_loading(False)
                    self._set_controls_enabled(True)
                    self.analyze_button.configure(text="Buscar videos")
                    self.download_all_button.configure(state="disabled")
                    self.bottom_action_button.configure(state="disabled")
                    self.search_results_heading.configure(
                        text="No se encontraron resultados"
                        if "No se encontraron videos" in error
                        else "No se pudo completar la búsqueda"
                    )
                    self.status.set("No se pudo completar la búsqueda.")
                    self._append_log(f"Error de búsqueda: {error}")
                    messagebox.showerror(
                        "Error al buscar en YouTube",
                        error,
                    )
                elif event == "metadata_failed":
                    self._set_loading(False)
                    self._set_controls_enabled(True)
                    self.analyze_button.configure(
                        text="Buscar videos"
                        if self.download_mode.get() == "search"
                        else "Analizar playlist"
                    )
                    self.download_all_button.configure(state="disabled")
                    self.bottom_action_button.configure(state="disabled")
                    self._set_action_text("Descargar todo en MP3")
                    self.status.set("No se pudo obtener la información.")
                    self._append_log(f"Error de metadatos: {value}")
                    if self.download_mode.get() == "search":
                        self.search_results_heading.configure(
                            text="No se pudo completar la búsqueda"
                        )
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
                elif event == "failure_log_written":
                    self._append_log(f"URLs fallidas guardadas en: {value}")
                elif event == "failure_log_failed":
                    self._append_log(f"No se pudo guardar el archivo de fallas: {value}")
                    messagebox.showerror(
                        "No se pudo guardar el registro de fallas",
                        f"Las canciones fallidas no se pudieron registrar.\n\n{value}",
                    )
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
