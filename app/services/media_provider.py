"""Adapter around yt-dlp and thumbnail retrieval."""

from __future__ import annotations

import queue
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import yt_dlp

MAX_SEARCH_RESULTS = 30
PREVIEW_RESOLUTIONS = (
    "Más baja",
    "Automática",
    "144p",
    "240p",
    "360p",
    "480p",
    "720p",
    "1080p",
)


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

    def search_videos(
        self,
        query: str,
        messages: queue.Queue[tuple[str, object]],
        limit: int = MAX_SEARCH_RESULTS,
    ) -> dict[str, Any] | None:
        """Search YouTube and return a bounded set of video metadata."""
        if not query.strip():
            raise ValueError("Escribe qué video quieres buscar.")
        if limit < 1:
            raise ValueError("La cantidad de resultados debe ser positiva.")
        limit = min(limit, MAX_SEARCH_RESULTS)
        options = {
            "skip_download": True,
            "noplaylist": False,
            "extract_flat": "in_playlist",
            "ignoreerrors": False,
            "socket_timeout": 10,
            "retries": 1,
            "quiet": True,
            "no_warnings": True,
            "logger": QueueLogger(messages),
        }
        with yt_dlp.YoutubeDL(options) as downloader:
            return downloader.extract_info(
                f"ytsearch{limit}:{query.strip()}",
                download=False,
            )

    def resolve_preview_stream(
        self,
        video_url: str,
        messages: queue.Queue[tuple[str, object]],
        max_height: int | None = None,
        prefer_lowest: bool = False,
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
        selected_format = self._select_preview_format(
            combined_formats, max_height, prefer_lowest
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

        stream = info.get("url")
        if (
            stream
            and not prefer_lowest
            and info.get("vcodec") not in (None, "none")
            and info.get("acodec") not in (None, "none")
            and (
                max_height is None
                or not info.get("height")
                or info.get("height") <= max_height
            )
        ):
            return stream, info.get("http_headers") or {}, None, {}

        requested_formats = info.get("requested_formats") or []
        selected_format = self._select_preview_format(
            [
                candidate
                for candidate in requested_formats
                if candidate.get("url")
                and candidate.get("vcodec") not in (None, "none")
                and candidate.get("acodec") not in (None, "none")
            ],
            max_height,
            prefer_lowest,
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
            video_format = self._select_preview_format(
                video_formats, max_height, prefer_lowest
            )
            if video_format is None:
                raise ValueError(
                    "yt-dlp no encontró un formato de video compatible para "
                    "la resolución seleccionada."
                )
            if prefer_lowest:
                audio_format = min(
                    audio_formats,
                    key=lambda candidate: (
                        candidate.get("abr")
                        or candidate.get("tbr")
                        or float("inf"),
                        candidate.get("protocol") not in {"https", "http"},
                    ),
                )
            else:
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

        if (
            stream
            and info.get("vcodec") not in (None, "none")
            and info.get("acodec") not in (None, "none")
            and (
                max_height is None
                or not info.get("height")
                or info.get("height") <= max_height
            )
        ):
            return stream, info.get("http_headers") or {}, None, {}

        raise ValueError(
            "yt-dlp no encontró formatos de video y audio compatibles para la "
            "vista previa. Actualiza yt-dlp y comprueba que el video se pueda "
            "reproducir desde el navegador."
        )

    @staticmethod
    def _select_preview_format(
        formats: list[dict[str, Any]],
        max_height: int | None,
        prefer_lowest: bool = False,
    ) -> dict[str, Any] | None:
        if not formats:
            return None
        candidates = formats
        if max_height is not None:
            known_heights = [
                candidate
                for candidate in formats
                if candidate.get("height")
            ]
            within_limit = [
                candidate
                for candidate in known_heights
                if candidate["height"] <= max_height
            ]
            if known_heights and not within_limit:
                return None
            candidates = within_limit or formats
        if prefer_lowest and max_height is None:
            return min(
                candidates,
                key=lambda candidate: (
                    candidate.get("height") or float("inf"),
                    candidate.get("tbr") or float("inf"),
                    candidate.get("protocol") not in {"https", "http"},
                ),
            )
        if max_height is not None:
            return max(
                candidates,
                key=lambda candidate: (
                    candidate.get("height") or 0,
                    candidate.get("protocol") in {"https", "http"},
                    candidate.get("tbr") or 0,
                ),
            )
        return max(
            candidates,
            key=lambda candidate: (
                candidate.get("protocol") in {"https", "http"},
                candidate.get("height") or 0,
                candidate.get("tbr") or 0,
            ),
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
        extractor = (info.get("ie_key") or info.get("extractor_key") or "").lower()
        video_id = info.get("id")
        if not thumbnail_url and extractor == "youtube" and video_id:
            thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        if not item_url:
            if candidate_url and urlsplit(candidate_url).scheme in {"http", "https"}:
                item_url = candidate_url
            elif extractor == "youtube":
                video_id = video_id or candidate_url
                if video_id:
                    item_url = (
                        f"https://www.youtube.com/watch?{urlencode({'v': video_id})}"
                    )
            elif candidate_url:
                item_url = candidate_url
        audio_tracks: dict[str, dict[str, Any]] = {}
        for media_format in info.get("formats") or []:
            language = media_format.get("language")
            if not language or media_format.get("acodec") in (None, "none"):
                continue
            track = audio_tracks.setdefault(language, {
                "language": language,
                "label": media_format.get("format_note") or language,
                "preference": media_format.get("language_preference") or -1,
            })
            if media_format.get("language_preference", -1) > track["preference"]:
                track["preference"] = media_format.get("language_preference")
                track["label"] = media_format.get("format_note") or language
        return {
            "title": info.get("title") or "Título desconocido",
            "artist": info.get("artist")
            or info.get("uploader")
            or info.get("channel")
            or "Audio",
            "duration": info.get("duration"),
            "thumbnail": thumbnail_url,
            "url": item_url,
            "audio_tracks": sorted(
                audio_tracks.values(),
                key=lambda track: (-track["preference"], track["language"]),
            ),
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
        audio_language: str | None = None,
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
            "format": (
                f"bestaudio[language={audio_language}]/bestaudio/best"
                if audio_language else "bestaudio/best"
            ),
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
