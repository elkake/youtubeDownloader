"""Optional VLC-backed video preview for selecting an audio clip."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import tkinter as tk


def is_vlc_available() -> bool:
    """Check whether both python-vlc and its native VLC runtime can load."""
    try:
        import_module("vlc")
    except (ImportError, OSError):
        return False
    return True


def create_video_player(
    video_frame: tk.Widget,
    stream_url: str,
    http_headers: dict[str, str],
    audio_stream_url: str | None = None,
    audio_http_headers: dict[str, str] | None = None,
) -> tuple[Any, Any]:
    """Create a VLC player attached to a Tk frame for video playback."""
    try:
        import vlc
    except ImportError as error:
        raise RuntimeError(
            "Falta la dependencia Python python-vlc. Desde la carpeta del "
            "proyecto ejecuta: python -m pip install -r requirements.txt"
        ) from error
    except OSError as error:
        raise RuntimeError(
            "No se encontró libvlc.dll. Instala VLC media player de 64 bits "
            "y vuelve a abrir youMP3gmr. Instalar los paquetes de Python no "
            "instala el reproductor VLC."
        ) from error

    try:
        instance = vlc.Instance("--no-video-title-show", "--quiet")
        if instance is None:
            raise RuntimeError("VLC no pudo inicializar su motor multimedia.")
        player = instance.media_player_new()
        media = instance.media_new(stream_url)
        for headers in (http_headers, audio_http_headers or {}):
            for header, value in headers.items():
                normalized = header.lower().replace("_", "-")
                if normalized in {"user-agent", "referer", "cookie"}:
                    media.add_option(f":http-{normalized}={value}")
        player.set_media(media)
        if audio_stream_url and player.add_slave(
            vlc.MediaSlaveType.audio, audio_stream_url, True
        ) != 0:
            raise RuntimeError("VLC no pudo añadir el audio a la vista previa.")
        video_frame.update_idletasks()
        if hasattr(player, "set_hwnd"):
            player.set_hwnd(video_frame.winfo_id())
        elif hasattr(player, "set_xwindow"):
            player.set_xwindow(video_frame.winfo_id())
        else:
            raise RuntimeError("VLC no admite insertar el video en esta ventana.")
        return instance, player
    except Exception as error:
        raise RuntimeError(
            "No se pudo iniciar la vista previa. Instala VLC media player "
            "de 64 bits y vuelve a abrir youMP3gmr."
        ) from error
