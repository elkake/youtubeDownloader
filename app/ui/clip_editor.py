"""Tkinter video preview and clip-range editor for individual tracks."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from typing import Callable

from app.services.video_preview import create_video_player


class ClipEditorWindow:
    """Preview one video, mark its start/end, and return the selected range."""

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        duration: float | None,
        stream_url: str,
        http_headers: dict[str, str],
        audio_stream_url: str | None,
        audio_http_headers: dict[str, str],
        palette: dict[str, str],
        on_apply: Callable[[tuple[float, float] | None], None],
    ) -> None:
        self.window = tk.Toplevel(parent)
        self.window.title(f"Editor de audio - {title}")
        icon_path = Path(__file__).resolve().parents[2] / "youMP3gmr.ico"
        if icon_path.is_file():
            self.window.iconbitmap(str(icon_path))
        self.window.geometry("760x600")
        self.window.minsize(600, 480)
        self.window.transient(parent)
        self.palette = palette
        self.on_apply = on_apply
        self.duration = max(1.0, float(duration or 1))
        self._updating_seek = False
        self.start_time = tk.StringVar(value="00:00")
        self.end_time = tk.StringVar(value=self._format_time(self.duration))
        self.playback_status = tk.StringVar(value="Conectando con el video...")
        self.window.configure(background=palette["background"])
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        container = ttk.Frame(self.window, padding=14)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)
        ttk.Label(
            container,
            text=title,
            style="ClipTitle.TLabel",
            font=("Segoe UI", 12, "bold"),
            wraplength=700,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.video_frame = tk.Frame(
            container,
            background="#000000",
            highlightthickness=0,
            borderwidth=0,
        )
        self.video_frame.grid(row=1, column=0, sticky="nsew")
        self.video_frame.configure(width=720, height=405)
        self.video_frame.grid_propagate(False)

        controls = ttk.Frame(container, style="Panel.TFrame", padding=10)
        controls.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        controls.columnconfigure(1, weight=1)
        self.play_button = ttk.Button(
            controls,
            text="▶ Reproducir",
            command=self.toggle_playback,
            style="Outline.TButton",
        )
        self.play_button.grid(row=0, column=0, padx=(0, 8))
        self.seek_value = tk.DoubleVar(value=0)
        self.seek_bar = ttk.Scale(
            controls,
            from_=0,
            to=self.duration,
            variable=self.seek_value,
            command=self._seek,
        )
        self.seek_bar.grid(row=0, column=1, sticky="ew")
        self.position_label = ttk.Label(
            controls,
            text=f"00:00 / {self._format_time(self.duration)}",
            style="PanelMuted.TLabel",
            width=16,
            anchor="e",
        )
        self.position_label.grid(row=0, column=2, padx=(8, 0))
        self.playback_label = ttk.Label(
            controls,
            textvariable=self.playback_status,
            style="PanelMuted.TLabel",
        )
        self.playback_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 8))

        range_controls = ttk.Frame(controls, style="Panel.TFrame")
        range_controls.grid(row=2, column=0, columnspan=3, sticky="ew")
        ttk.Label(range_controls, text="Desde", style="PanelMuted.TLabel").pack(
            side="left"
        )
        self.start_entry = ttk.Entry(
            range_controls, textvariable=self.start_time, width=10
        )
        self.start_entry.pack(side="left", padx=(5, 6))
        ttk.Button(
            range_controls,
            text="Marcar inicio",
            command=self.mark_start,
            style="Outline.TButton",
        ).pack(side="left", padx=(0, 14))
        ttk.Label(range_controls, text="Hasta", style="PanelMuted.TLabel").pack(
            side="left"
        )
        self.end_entry = ttk.Entry(
            range_controls, textvariable=self.end_time, width=10
        )
        self.end_entry.pack(side="left", padx=(5, 6))
        ttk.Button(
            range_controls,
            text="Marcar fin",
            command=self.mark_end,
            style="Outline.TButton",
        ).pack(side="left")

        actions = ttk.Frame(container, style="App.TFrame")
        actions.grid(row=3, column=0, sticky="e", pady=(12, 0))
        ttk.Button(
            actions,
            text="Usar audio completo",
            command=self._use_full_audio,
            style="Outline.TButton",
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="Descargar fragmento",
            command=self._apply_range,
            style="Primary.TButton",
        ).pack(side="left")

        try:
            self.instance, self.player = create_video_player(
                self.video_frame,
                stream_url,
                http_headers,
                audio_stream_url,
                audio_http_headers,
            )
        except RuntimeError:
            self.window.destroy()
            raise
        self.window.after(100, self._start_playback)
        self.window.after(200, self._update_playback)
        self.window.bind("<space>", self._space_to_toggle)

    @staticmethod
    def _format_time(seconds: float) -> str:
        total_milliseconds = max(0, round(seconds * 1000))
        hours, remainder = divmod(total_milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        if hours:
            return (
                f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}."
                f"{milliseconds:03d}"
            )
        return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"

    @staticmethod
    def _parse_time(value: str) -> float:
        parts = value.strip().split(":")
        if not 1 <= len(parts) <= 3:
            raise ValueError("Usa segundos, MM:SS o HH:MM:SS.")
        try:
            numbers = [float(part) for part in parts]
        except ValueError as error:
            raise ValueError("El tiempo debe contener números válidos.") from error
        if any(number < 0 for number in numbers):
            raise ValueError("El tiempo no puede ser negativo.")
        if len(numbers) == 1:
            return round(numbers[0] * 1000) / 1000
        if len(numbers) == 2:
            minutes, seconds = numbers
            if seconds >= 60:
                raise ValueError("Los segundos deben ser menores que 60.")
            return round((minutes * 60 + seconds) * 1000) / 1000
        hours, minutes, seconds = numbers
        if minutes >= 60 or seconds >= 60:
            raise ValueError("Minutos y segundos deben ser menores que 60.")
        return round((hours * 3600 + minutes * 60 + seconds) * 1000) / 1000

    def _start_playback(self) -> None:
        if not self.window.winfo_exists():
            return
        result = self.player.play()
        if result == -1:
            self.playback_status.set("VLC no pudo iniciar la reproducción.")
        else:
            self.play_button.configure(text="Ⅱ Pausar")

    def toggle_playback(self) -> None:
        if self.player.is_playing():
            self.player.pause()
            self.play_button.configure(text="▶ Reproducir")
        elif self.player.play() == -1:
            self.playback_status.set("No se pudo reproducir el video.")
        else:
            self.play_button.configure(text="Ⅱ Pausar")

    def _space_to_toggle(self, _event: tk.Event) -> str:
        if self.window.focus_get() not in (self.start_entry, self.end_entry):
            self.toggle_playback()
            return "break"
        return ""

    def _seek(self, value: str) -> None:
        if self._updating_seek:
            return
        if self.player.is_playing() or self.player.get_length() > 0:
            self.player.set_time(int(float(value) * 1000))

    def _update_playback(self) -> None:
        if not self.window.winfo_exists():
            return
        current_ms = self.player.get_time()
        if current_ms >= 0:
            current = current_ms / 1000
            self._updating_seek = True
            self.seek_value.set(current)
            self._updating_seek = False
            self.position_label.configure(
                text=f"{self._format_time(current)} / {self._format_time(self.duration)}"
            )
        state = self.player.get_state()
        if state == 7:
            self.playback_status.set(
                "No se pudo reproducir el video. Comprueba VLC y vuelve a intentarlo."
            )
        self.window.after(200, self._update_playback)

    def mark_start(self) -> None:
        self.start_time.set(
            self._format_time(max(0, self.player.get_time()) / 1000)
        )

    def mark_end(self) -> None:
        self.end_time.set(
            self._format_time(max(0, self.player.get_time()) / 1000)
        )

    def _apply_range(self) -> None:
        try:
            start = self._parse_time(self.start_time.get())
            end = self._parse_time(self.end_time.get())
            if start >= end:
                raise ValueError("El final debe ser posterior al inicio.")
            if end > self.duration:
                raise ValueError("El final supera la duración del video.")
        except ValueError as error:
            messagebox.showerror("Rango no válido", str(error), parent=self.window)
            return
        self.on_apply((start, end))
        self.close()

    def _use_full_audio(self) -> None:
        self.on_apply(None)
        self.close()

    def close(self) -> None:
        try:
            self.player.stop()
            self.instance.release()
        finally:
            self.window.destroy()
