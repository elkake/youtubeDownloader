"""Load and save user preferences outside the application directory."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.services.media_provider import PREVIEW_RESOLUTIONS


def settings_file_path() -> Path:
    app_data = os.environ.get("APPDATA")
    settings_directory = (
        Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
    )
    return settings_directory / "youMP3gmr" / "settings.json"


def validate_music_styles(values: Any) -> list[str]:
    if not isinstance(values, list):
        raise ValueError("La lista de estilos musicales guardada no es válida.")
    styles: list[str] = []
    seen: set[str] = set()
    invalid_characters = '<>:"/\\|?*'
    for value in values:
        if not isinstance(value, str):
            raise ValueError("Cada estilo musical debe ser texto.")
        style = value.strip()
        if (
            not style
            or style.casefold() == "sin estilo"
            or len(style) > 60
            or style in {".", ".."}
            or any(
                ord(character) < 32 or character in invalid_characters
                for character in style
            )
            or style.endswith((".", " "))
        ):
            raise ValueError(f"El nombre de estilo no es válido: {style!r}.")
        if style.casefold() in seen:
            raise ValueError(f"El estilo «{style}» está repetido.")
        if style.split(".", 1)[0].upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{number}" for number in range(1, 10)),
            *(f"LPT{number}" for number in range(1, 10)),
        }:
            raise ValueError(f"El nombre de estilo «{style}» está reservado.")
        seen.add(style.casefold())
        styles.append(style)
    return styles


def load_settings(
    default_output_directory: Path,
) -> tuple[dict[str, str | int | list[str]], str | None]:
    defaults: dict[str, str | int | list[str]] = {
        "output_directory": str(default_output_directory),
        "preview_resolution": "Más baja",
        "preview_volume": 100,
        "concurrent_downloads": 2,
        "music_styles": [],
    }
    path = settings_file_path()
    if not path.exists():
        return defaults, None
    try:
        values: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("El archivo de preferencias no contiene un objeto.")
        output_directory = values.get("output_directory", defaults["output_directory"])
        resolution = values.get("preview_resolution", defaults["preview_resolution"])
        volume = values.get("preview_volume", defaults["preview_volume"])
        concurrent_downloads = values.get(
            "concurrent_downloads", defaults["concurrent_downloads"]
        )
        music_styles = validate_music_styles(
            values.get("music_styles", defaults["music_styles"])
        )
        if not isinstance(output_directory, str) or not output_directory.strip():
            raise ValueError("La carpeta de descarga guardada no es válida.")
        if resolution not in PREVIEW_RESOLUTIONS:
            raise ValueError("La resolución de reproducción guardada no es válida.")
        if (
            isinstance(volume, bool)
            or not isinstance(volume, int)
            or not 0 <= volume <= 100
        ):
            raise ValueError("El volumen guardado debe estar entre 0 y 100.")
        if (
            isinstance(concurrent_downloads, bool)
            or not isinstance(concurrent_downloads, int)
            or not 2 <= concurrent_downloads <= 16
        ):
            raise ValueError(
                "Las descargas simultáneas deben estar entre 2 y 16."
            )
        return {
            "output_directory": output_directory,
            "preview_resolution": resolution,
            "preview_volume": volume,
            "concurrent_downloads": concurrent_downloads,
            "music_styles": music_styles,
        }, None
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return defaults, f"No se pudieron leer las preferencias guardadas: {error}"


def save_settings(
    output_directory: str,
    preview_resolution: str,
    preview_volume: int,
    concurrent_downloads: int,
    music_styles: list[str],
) -> None:
    if not output_directory.strip():
        raise ValueError("Elige una carpeta de descarga.")
    if preview_resolution not in PREVIEW_RESOLUTIONS:
        raise ValueError("Selecciona una resolución de reproducción válida.")
    if (
        isinstance(preview_volume, bool)
        or not isinstance(preview_volume, int)
        or not 0 <= preview_volume <= 100
    ):
        raise ValueError("El volumen debe estar entre 0 y 100.")
    if (
        isinstance(concurrent_downloads, bool)
        or not isinstance(concurrent_downloads, int)
        or not 2 <= concurrent_downloads <= 16
    ):
        raise ValueError("Las descargas simultáneas deben estar entre 2 y 16.")
    validated_styles = validate_music_styles(music_styles)
    path = settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "output_directory": output_directory,
                "preview_resolution": preview_resolution,
                "preview_volume": preview_volume,
                "concurrent_downloads": concurrent_downloads,
                "music_styles": validated_styles,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
