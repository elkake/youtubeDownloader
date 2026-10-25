"""Reusable UI controls."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Any

from app.ui.image_adapter import create_rounded_button_image


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Any,
        palette: dict[str, str],
        variant: str = "primary",
        width: int | None = None,
        height: int = 38,
        state: str = "normal",
        background_role: str = "background",
        **options: Any,
    ) -> None:
        options.pop("style", None)
        options.pop("padding", None)
        options.pop("font", None)
        self.font = tkfont.Font(family="Segoe UI", size=9, weight="bold")
        self.horizontal_padding = 16
        self.background_role = background_role
        self.preferred_width = self._measure_width(text, width)
        self.preferred_height = height
        super().__init__(
            parent,
            width=self.preferred_width,
            height=height,
            background=palette[background_role],
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2" if state == "normal" else "arrow",
            takefocus=True,
            **options,
        )
        self.text = text
        self.command = command
        self.palette = palette
        self.variant = variant
        self.enabled = state == "normal"
        self.hovered = False
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Return>", self._on_key)
        self.bind("<space>", self._on_key)
        self._draw()

    def configure(self, cnf: Any = None, **options: Any) -> Any:
        """Accept the text/state options used by ttk.Button call sites."""
        text = options.pop("text", None)
        state = options.pop("state", None)
        if text is not None:
            self.text = text
            self.preferred_width = self._measure_width(text, None)
            super().configure(width=self.preferred_width)
        if state is not None:
            self.enabled = state != "disabled"
            super().configure(cursor="hand2" if self.enabled else "arrow")
        if options:
            return super().configure(cnf, **options)
        if cnf is not None:
            return super().configure(cnf)
        self._draw()
        return None

    config = configure

    def _measure_width(self, text: str, width: int | None) -> int:
        if width is not None:
            return max(32, self.font.measure("0" * width) + self.horizontal_padding)
        return max(32, self.font.measure(text) + self.horizontal_padding * 2)

    def set_text(self, text: str) -> None:
        self.configure(text=text)

    def set_enabled(self, enabled: bool) -> None:
        self.configure(state="normal" if enabled else "disabled")

    def set_palette(self, palette: dict[str, str]) -> None:
        self.palette = palette
        super().configure(background=palette[self.background_role])
        self._draw()

    def _draw(self, _event: tk.Event | None = None) -> None:
        self.delete("all")
        width = max(self.winfo_width(), self.preferred_width)
        height = max(self.winfo_height(), self.preferred_height)

        if not self.enabled:
            fill = self.palette["disabled"]
            foreground = self.palette["muted"]
            outline = None
        elif self.variant == "danger":
            fill = self.palette["danger"]
            foreground = self.palette["primary_text"]
            outline = None
        elif self.variant == "primary":
            fill = self.palette["primary_hover"] if self.hovered else self.palette["primary"]
            foreground = self.palette["primary_text"]
            outline = None
        else:
            fill = self.palette["surface_hover"] if self.hovered else self.palette["surface"]
            foreground = self.palette["text"]
            outline = self.palette["border"]

        self._button_image = create_rounded_button_image(
            width,
            height,
            self.palette[self.background_role],
            fill,
            outline,
        )
        self.create_image(0, 0, anchor="nw", image=self._button_image)
        self.create_text(
            width // 2,
            height // 2,
            text=self.text,
            fill=foreground,
            font=self.font,
        )

    def _on_enter(self, _event: tk.Event) -> None:
        self.hovered = self.enabled
        self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hovered = False
        self._draw()

    def _on_click(self, _event: tk.Event) -> None:
        if self.enabled:
            self.focus_set()
            self.command()

    def _on_key(self, _event: tk.Event) -> None:
        if self.enabled:
            self.command()


class RoundedEntry(tk.Canvas):
    """Entry field with a rounded border and a native editable text control."""

    def __init__(
        self,
        parent: tk.Widget,
        textvariable: tk.StringVar,
        palette: dict[str, str],
    ) -> None:
        self.palette = palette
        super().__init__(
            parent,
            height=36,
            background=palette["surface"],
            borderwidth=0,
            highlightthickness=0,
        )
        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            background=palette["field"],
            foreground=palette["text"],
            insertbackground=palette["text"],
            selectbackground=palette["primary"],
            selectforeground=palette["primary_text"],
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.window = self.create_window(7, 7, anchor="nw", window=self.entry)
        self._border_image = None
        self.bind("<Configure>", self._resize_entry)
        self.entry.bind("<FocusIn>", self._draw_border)
        self.entry.bind("<FocusOut>", self._draw_border)
        self._draw_border()

    def configure(self, cnf: Any = None, **options: Any) -> Any:
        state = options.pop("state", None)
        if state is not None:
            self.entry.configure(state=state)
        if options:
            return super().configure(cnf, **options)
        if cnf is not None:
            return super().configure(cnf)
        return None

    config = configure

    def focus_set(self) -> None:
        self.entry.focus_set()

    def set_palette(self, palette: dict[str, str]) -> None:
        self.palette = palette
        self.configure(background=palette["surface"])
        self.entry.configure(
            background=palette["field"],
            foreground=palette["text"],
            insertbackground=palette["text"],
            selectbackground=palette["primary"],
            selectforeground=palette["primary_text"],
        )
        self._draw_border()

    def _resize_entry(self, event: tk.Event) -> None:
        self.itemconfigure(self.window, width=max(1, event.width - 10))
        self._draw_border()

    def _draw_border(self, _event: tk.Event | None = None) -> None:
        self._border_image = create_rounded_button_image(
            max(1, self.winfo_width()),
            max(1, self.winfo_height()),
            self.palette["surface"],
            self.palette["field"],
            self.palette["border"],
        )
        self.delete("rounded-border")
        self.create_image(
            0,
            0,
            anchor="nw",
            image=self._border_image,
            tags=("rounded-border",),
        )
        self.tag_lower("rounded-border", self.window)


class SubtleScrollbar(tk.Canvas):
    """A narrow, quiet scrollbar with a rounded thumb matching the current theme."""

    def __init__(
        self,
        parent: tk.Widget,
        command: Any,
        palette: dict[str, str],
    ) -> None:
        super().__init__(
            parent,
            width=12,
            background=palette["surface"],
            borderwidth=0,
            highlightthickness=0,
            cursor="arrow",
        )
        self.command = command
        self.palette = palette
        self.first = 0.0
        self.last = 1.0
        self._drag_offset = 0
        self.bind("<Configure>", self._draw)
        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.hovered = False

    def set(self, first: str | float, last: str | float) -> None:
        self.first = float(first)
        self.last = float(last)
        self._draw()

    def set_palette(self, palette: dict[str, str]) -> None:
        self.palette = palette
        super().configure(background=palette["surface"])
        self._draw()

    def _thumb_bounds(self) -> tuple[float, float]:
        height = max(self.winfo_height(), 1)
        top = self.first * height
        bottom = max(top + 28, self.last * height)
        return min(top, height - 28), min(bottom, height)

    def _draw(self, _event: tk.Event | None = None) -> None:
        self.delete("all")
        if self.last >= 1.0 and self.first <= 0.0:
            return
        top, bottom = self._thumb_bounds()
        thumb_color = (
            self.palette["muted"] if self.hovered else self.palette["border"]
        )
        self.create_line(
            6,
            top + 7,
            6,
            max(top + 7, bottom - 7),
            fill=thumb_color,
            width=5 if self.hovered else 4,
            capstyle=tk.ROUND,
            tags=("thumb",),
        )

    def _on_enter(self, _event: tk.Event) -> None:
        self.hovered = True
        self._draw()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hovered = False
        self._draw()

    def _on_click(self, event: tk.Event) -> None:
        top, bottom = self._thumb_bounds()
        if top <= event.y <= bottom:
            self._drag_offset = event.y - top
        else:
            thumb_height = bottom - top
            self._drag_offset = thumb_height / 2
            self.command(
                "moveto",
                max(
                    0.0,
                    min(
                        1.0,
                        (event.y - self._drag_offset)
                        / max(self.winfo_height() - thumb_height, 1),
                    ),
                ),
            )

    def _on_drag(self, event: tk.Event) -> None:
        height = max(self.winfo_height(), 1)
        self.command(
            "moveto",
            max(0.0, min(1.0, (event.y - self._drag_offset) / height)),
        )
