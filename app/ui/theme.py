"""Applies and switches the application color themes."""

from __future__ import annotations

from app.config.theme import DARK_PALETTE, LIGHT_PALETTE


class ThemeMixin:
    """Applies and switches the application color themes."""

    def _get_palette(self) -> dict[str, str]:
        return DARK_PALETTE if self.theme == "dark" else LIGHT_PALETTE

    def _apply_theme(self) -> None:
        colors = self.palette
        self.root.configure(background=colors["background"])
        self.style.configure("TFrame", background=colors["background"])
        self.style.configure("App.TFrame", background=colors["background"])
        self.style.configure(
            "AppTitle.TLabel",
            background=colors["background"],
            foreground=colors["text"],
        )
        self.style.configure("Panel.TFrame", background=colors["surface"])
        self.style.configure("TableHeader.TFrame", background=colors["surface_hover"])
        self.style.configure("QueueRow.TFrame", background=colors["surface"])
        self.style.configure(
            "TLabel", background=colors["background"], foreground=colors["text"]
        )
        self.style.configure(
            "Panel.TLabel", background=colors["surface"], foreground=colors["text"]
        )
        self.style.configure(
            "PanelMuted.TLabel",
            background=colors["surface"],
            foreground=colors["muted"],
        )
        self.style.configure(
            "Muted.TLabel",
            background=colors["background"],
            foreground=colors["muted"],
        )
        self.style.configure(
            "SummaryTitle.TLabel",
            background=colors["surface"],
            foreground=colors["text"],
        )
        self.style.configure(
            "SearchPageTitle.TLabel",
            background=colors["background"],
            foreground=colors["text"],
        )
        self.style.configure(
            "Path.TLabel",
            background=colors["field"],
            foreground=colors["muted"],
        )
        self.style.configure(
            "TableHeading.TLabel",
            background=colors["surface_hover"],
            foreground=colors["muted"],
        )
        self.style.configure(
            "FooterTitle.TLabel",
            background=colors["background"],
            foreground=colors["text"],
            font=("Segoe UI", 9, "bold"),
        )
        self.style.configure(
            "QueueIcon.TLabel",
            background=colors["background"],
            foreground=colors["danger"],
        )
        self.style.configure(
            "Cover.TLabel",
            background=colors["selected"],
            foreground=colors["cyan"],
            font=("Segoe UI", 24, "bold"),
        )
        self.style.configure(
            "Badge.TLabel",
            background=colors["selected"],
            foreground=colors["danger"],
            font=("Segoe UI", 8, "bold"),
        )
        self.style.configure(
            "Quality.TLabel",
            background=colors["selected"],
            foreground=colors["cyan"],
        )
        self.style.configure(
            "QueueStatus.TLabel",
            background=colors["surface"],
            foreground=colors["danger"],
        )
        self.style.configure(
            "CompleteStatus.TLabel",
            background=colors["surface"],
            foreground=colors["cyan"],
        )
        self.style.configure(
            "Engine.TLabel",
            background=colors["selected"],
            foreground=colors["cyan"],
            font=("Segoe UI", 8, "bold"),
        )
        self.style.configure(
            "TLabelframe",
            background=colors["background"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            relief="solid",
        )
        self.style.configure(
            "TLabelFrame", background=colors["background"], foreground=colors["text"]
        )
        self.style.configure(
            "TLabelframe.Label",
            background=colors["background"],
            foreground=colors["text"],
        )
        self.style.configure(
            "Card.TLabelframe",
            background=colors["surface"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            relief="solid",
        )
        self.style.configure(
            "Card.TLabelframe.Label",
            background=colors["surface"],
            foreground=colors["muted"],
        )
        self.style.configure(
            "Card.TLabel",
            background=colors["surface"],
            foreground=colors["text"],
        )
        self.style.configure(
            "CardTitle.TLabel",
            background=colors["surface"],
            foreground=colors["text"],
        )
        self.style.configure(
            "TButton",
            background=colors["surface_hover"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(10, 6),
            relief="flat",
            focusthickness=0,
        )
        self.style.configure(
            "Icon.TButton",
            background=colors["surface"],
            foreground=colors["muted"],
            bordercolor=colors["surface"],
            padding=(2, 2),
        )
        self.style.configure(
            "Primary.TButton",
            background=colors["danger"],
            foreground="#FFFFFF",
            bordercolor=colors["danger"],
            padding=(10, 7),
            font=("Segoe UI", 9, "bold"),
        )
        self.style.map(
            "Primary.TButton",
            background=[
                ("disabled", colors["disabled"]),
                ("active", colors["accent"]),
            ],
            foreground=[("disabled", colors["muted"])],
        )
        self.style.configure(
            "Outline.TButton",
            background=colors["surface_hover"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            padding=(9, 6),
        )
        self.style.map(
            "Outline.TButton",
            background=[
                ("disabled", colors["surface"]),
                ("active", colors["border"]),
            ],
            foreground=[("disabled", colors["muted"])],
        )
        self.style.map(
            "TButton",
            background=[("disabled", colors["surface"]), ("active", colors["border"])],
            foreground=[("disabled", colors["muted"])],
        )
        for button_style, background, foreground in (
            ("Primary.TButton", colors["danger"], "#FFFFFF"),
            ("Outline.TButton", colors["surface_hover"], colors["text"]),
        ):
            self.style.configure(
                button_style,
                background=background,
                foreground=foreground,
                bordercolor=background if "Primary" in button_style else colors["border"],
                padding=(10, 6),
                relief="flat",
            )
            self.style.map(
                button_style,
                background=[
                    ("disabled", colors["surface"]),
                    ("active", colors["accent"] if "Primary" in button_style else colors["border"]),
                ],
                foreground=[("disabled", colors["muted"])],
            )
        self.style.configure(
            "TEntry",
            fieldbackground=colors["field"],
            foreground=colors["text"],
            insertcolor=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=7,
        )
        self.style.map(
            "TEntry",
            bordercolor=[("focus", colors["muted"])],
            lightcolor=[("focus", colors["muted"])],
            darkcolor=[("focus", colors["muted"])],
        )
        self.style.configure(
            "TRadiobutton",
            background=colors["background"],
            foreground=colors["text"],
            focuscolor=colors["background"],
            indicatorcolor=colors["surface"],
        )
        self.style.configure(
            "Panel.TCheckbutton",
            background=colors["surface"],
            foreground=colors["text"],
            indicatorcolor=colors["surface_hover"],
        )
        self.style.map(
            "Panel.TCheckbutton",
            background=[("active", colors["surface"])],
            foreground=[("disabled", colors["muted"])],
            indicatorcolor=[
                ("selected", colors["danger"]),
                ("!selected", colors["surface_hover"]),
            ],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=colors["field"],
            background=colors["surface_hover"],
            foreground=colors["text"],
            arrowcolor=colors["muted"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
        )
        self.style.map(
            "TRadiobutton",
            background=[("active", colors["background"])],
            foreground=[("disabled", colors["muted"])],
            indicatorcolor=[
                ("selected", colors["primary"]),
                ("!selected", colors["surface"]),
            ],
        )
        self.style.configure(
            "Horizontal.TProgressbar",
            background=colors["progress"],
            troughcolor=colors["trough"],
            bordercolor=colors["trough"],
            lightcolor=colors["progress"],
            darkcolor=colors["progress"],
        )
        self.style.configure(
            "Queue.Horizontal.TProgressbar",
            background=colors["cyan"],
            troughcolor=colors["trough"],
            bordercolor=colors["trough"],
            lightcolor=colors["cyan"],
            darkcolor=colors["cyan"],
        )
        self.canvas.configure(background=colors["surface"])
        self.search_canvas.configure(background=colors["surface"])
        self.search_queue_canvas.configure(background=colors["surface"])
        self.scrollbar.set_palette(colors)
        self.search_scrollbar.set_palette(colors)
        self.search_queue_scrollbar.set_palette(colors)
        self.url_entry.set_palette(colors)
        self.search_entry.set_palette(colors)
        self._update_empty_state()
        self.canvas.itemconfigure("empty-state", fill=colors["muted"])
        self.playlist_cover.configure(style="Cover.TLabel")
        self.playlist_badge.configure(style="Badge.TLabel")
        self.engine_status.configure(style="Engine.TLabel")
        for button in (
            self.minimize_button,
            self.maximize_button,
            self.close_button,
        ):
            button.set_palette(colors)
        self.log.configure(
            background=colors["surface"],
            foreground=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["primary"],
            selectforeground=colors["primary_text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=colors["border"],
        )
        for button in self.rounded_buttons:
            button.set_palette(colors)

    def _toggle_theme(self) -> None:
        self.theme = "dark" if self.theme == "light" else "light"
        self.palette = self._get_palette()
        self._apply_theme()
        self.theme_button.set_text(
            "Tema claro" if self.theme == "dark" else "Tema oscuro"
        )
