"""Pillow adapter for rendering images used by the desktop interface."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tkinter import PhotoImage

from PIL import Image, ImageDraw, ImageTk


def create_rounded_button_image(
    width: int,
    height: int,
    background: str,
    fill: str,
    outline: str | None,
) -> PhotoImage:
    """Render a rounded button surface at a higher resolution for smooth edges."""
    width = max(width, 3)
    height = max(height, 3)
    scale = 3
    image = Image.new(
        "RGB",
        (width * scale, height * scale),
        background,
    )
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (scale, scale, (width - 1) * scale, (height - 1) * scale),
        radius=8 * scale,
        fill=fill,
        outline=outline,
        width=scale if outline else 1,
    )
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(resized)


def create_thumbnail(image_data: bytes, size: tuple[int, int]) -> PhotoImage:
    """Decode and resize thumbnail bytes for display by a Tk widget."""
    image = Image.open(BytesIO(image_data)).convert("RGB")
    image.thumbnail(size)
    return ImageTk.PhotoImage(image)


def create_app_icon(path: Path, size: tuple[int, int]) -> PhotoImage:
    """Load and scale the application ICO for use in the custom title strip."""
    with Image.open(path) as source:
        image = source.convert("RGBA")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)
