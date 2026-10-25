"""Adapter around yt-dlp and thumbnail retrieval."""

from __future__ import annotations

import queue
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import yt_dlp


class QueueLogger:
    """Routes yt-dlp messages through the UI's thread-safe event queue."""

    def __init__(self, messages: queue.Queue[tuple[str, object]]) -> None:
        self.messages = messages

    def debug(self, message: str) -> None:
        if message.strip():
            self.messages.put(("log", message))

    def info(self, message: str) -> None:
        if message.strip():
            self.messages.put(("log", message))

    def warning(self, message: str) -> None:
        if message.strip():
            self.messages.put(("log", f"Advertencia: {message}"))

    def error(self, message: str) -> None:
        if message.strip():
            self.messages.put(("log", f"Error: {message}"))


class YtDlpMediaProvider:
    """Hides yt-dlp options behind a small replaceable media-provider API."""

    def resolve_preview_stream(
        self,
        video_url: str,
        messages: queue.Queue[tuple[str, object]],
    ) -> tuple[str, dict[str, str], str | None, dict[str, str]]:
        """Resolve preview video and, if needed, its separate audio stream."""
        options = {
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "logger": QueueLogger(messages),
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(video_url, download=False)
        if not info:
            raise ValueError("No se pudo encontrar el video para la vista previa.")

        formats = info.get("formats") or []
        combined_formats = [
            candidate
            for candidate in formats
            if candidate.get("url")
            and candidate.get("vcodec") not in (None, "none")
            and candidate.get("acodec") not in (None, "none")
        ]
        if combined_formats:
            selected_format = max(
                combined_formats,
                key=lambda candidate: (
                    candidate.get("protocol") in {"https", "http"},
                    candidate.get("height") or 0,
                    candidate.get("tbr") or 0,
                ),
            )
            return (
                selected_format["url"],
                selected_format.get("http_headers")
                or info.get("http_headers")
                or {},
                None,
                {},
            )

        stream = info.get("url")
        if stream and info.get("vcodec") not in (None, "none") and info.get(
            "acodec"
        ) not in (None, "none"):
            return stream, info.get("http_headers") or {}, None, {}

        requested_formats = info.get("requested_formats") or []
        selected_format = next(
            (
                candidate
                for candidate in requested_formats
                if candidate.get("url")
                and candidate.get("vcodec") not in (None, "none")
                and candidate.get("acodec") not in (None, "none")
            ),
            None,
        )
        if selected_format:
            return (
                selected_format["url"],
                selected_format.get("http_headers")
                or info.get("http_headers")
                or {},
                None,
                {},
            )
        video_formats = [
            candidate
            for candidate in formats
            if candidate.get("url") and candidate.get("vcodec") not in (None, "none")
        ]
        audio_formats = [
            candidate
            for candidate in formats
            if candidate.get("url") and candidate.get("acodec") not in (None, "none")
        ]
        if video_formats and audio_formats:
            video_format = max(
                video_formats,
                key=lambda candidate: (
                    candidate.get("protocol") in {"https", "http"},
                    candidate.get("height") or 0,
                    candidate.get("tbr") or 0,
                ),
            )
            audio_format = max(
                audio_formats,
                key=lambda candidate: (
                    candidate.get("protocol") in {"https", "http"},
                    candidate.get("abr") or 0,
                    candidate.get("tbr") or 0,
                ),
            )
            return (
                video_format["url"],
                video_format.get("http_headers") or info.get("http_headers") or {},
                audio_format["url"],
                audio_format.get("http_headers") or info.get("http_headers") or {},
            )

        raise ValueError(
            "yt-dlp no encontró formatos de video y audio compatibles para la "
            "vista previa. Actualiza yt-dlp y comprueba que el video se pueda "
            "reproducir desde el navegador."
        )

    def extract_metadata(
        self,
        url: str,
        single_video: bool,
        messages: queue.Queue[tuple[str, object]],
    ) -> dict[str, Any] | None:
        """Read video or playlist metadata without downloading media."""
        options = {
            "skip_download": True,
            "noplaylist": single_video,
            "ignoreerrors": False,
            "logger": QueueLogger(messages),
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            return downloader.extract_info(url, download=False)

    @staticmethod
    def normalize_metadata(info: dict[str, Any]) -> dict[str, Any]:
        """Convert extractor-specific fields into the queue's stable item format."""
        thumbnails = info.get("thumbnails") or []
        thumbnail_url = info.get("thumbnail")
        if thumbnails:
            best_thumbnail = max(
                thumbnails,
                key=lambda item: (item.get("width") or 0) * (item.get("height") or 0),
            )
            thumbnail_url = best_thumbnail.get("url") or thumbnail_url
        item_url = info.get("webpage_url") or info.get("original_url")
        candidate_url = info.get("url")
        if not item_url and candidate_url:
            if urlsplit(candidate_url).scheme in {"http", "https"}:
                item_url = candidate_url
            elif (info.get("ie_key") or info.get("extractor_key", "")).lower() == "youtube":
                video_id = info.get("id") or candidate_url
                item_url = f"https://www.youtube.com/watch?{urlencode({'v': video_id})}"
            else:
                item_url = candidate_url
        return {
            "title": info.get("title") or "Título desconocido",
            "artist": info.get("artist")
            or info.get("uploader")
            or info.get("channel")
            or "Audio",
            "duration": info.get("duration"),
            "thumbnail": thumbnail_url,
            "url": item_url,
        }

    @staticmethod
    def fetch_thumbnail(url: str | None) -> bytes | None:
        """Fetch a bounded amount of thumbnail data for safe UI-side decoding."""
        if not url:
            return None
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=8) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("la imagen supera el límite de 2 MB")
        return data

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Apply yt-dlp's cross-platform filename sanitization."""
        return yt_dlp.utils.sanitize_filename(name)

    def download_audio(
        self,
        video_url: str,
        output_path: Path,
        progress_hook: Callable[[dict[str, Any]], None],
        messages: queue.Queue[tuple[str, object]],
        embed_metadata: bool = True,
        clip_section: tuple[float, float] | None = None,
    ) -> Path | None:
        """Download a track and optionally embed its cover and audio metadata."""
        final_path: Path | None = None

        def capture_postprocessed_path(data: dict[str, Any]) -> None:
            nonlocal final_path
            if data.get("status") != "finished":
                return
            info = data.get("info_dict") or {}
            filepath = info.get("filepath")
            if filepath:
                final_path = Path(filepath)

        postprocessors: list[dict[str, Any]] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
        if embed_metadata:
            postprocessors.extend(
                [
                    {"key": "FFmpegMetadata"},
                    {"key": "EmbedThumbnail"},
                ]
            )

        options = {
            "format": "bestaudio/best",
            "outtmpl": str(output_path),
            "noplaylist": True,
            "ignoreerrors": False,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "writethumbnail": embed_metadata,
            "logger": QueueLogger(messages),
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [capture_postprocessed_path],
            "postprocessors": postprocessors,
        }
        if embed_metadata:
            options["postprocessor_args"] = {
                "embedthumbnail+ffmpeg_o": [
                    "-c:v",
                    "mjpeg",
                    "-vf",
                    "scale=300:300:force_original_aspect_ratio=increase,crop=300:300",
                ]
            }
        if clip_section is not None:
            start, end = clip_section
            if start < 0 or end <= start:
                raise ValueError("El rango de recorte no es válido.")
            options["download_ranges"] = yt_dlp.utils.download_range_func(
                None, [(start, end)]
            )
            options["force_keyframes_at_cuts"] = True
        with yt_dlp.YoutubeDL(options) as downloader:
            downloader.download([video_url])
        return final_path
