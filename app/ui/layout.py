"""Builds and updates the application widgets and playlist queue."""

from __future__ import annotations

from tkinter import filedialog, messagebox, ttk
import tkinter as tk
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.ui.image_adapter import create_app_icon, create_thumbnail
from app.ui.widgets import RoundedButton, RoundedEntry, SubtleScrollbar


class LayoutMixin:
    """Builds and updates the application widgets and playlist queue."""

    def _create_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Any = lambda: None,
        variant: str = "outline",
        background_role: str = "background",
        **options: Any,
    ) -> RoundedButton:
        button = RoundedButton(
            parent,
            text=text,
            command=command,
            palette=self.palette,
            variant=variant,
            background_role=background_role,
            **options,
        )
        self.rounded_buttons.append(button)
        return button

    def _build_interface(self) -> None:
        title_bar = ttk.Frame(self.root, style="App.TFrame", padding=(10, 3))
        title_bar.configure(height=38)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        title_bar.bind("<ButtonPress-1>", self._start_window_drag)
        self.brand_icon = create_app_icon(self.app_icon_path, (24, 24))
        brand = ttk.Label(
            title_bar,
            text="youMP3gmr",
            image=self.brand_icon,
            compound="left",
            style="AppTitle.TLabel",
            font=("Segoe UI", 9, "bold"),
            padding=(0, 0, 0, 0),
        )
        brand.pack(side="left", padx=(2, 10), ipady=2)
        brand.bind("<ButtonPress-1>", self._start_window_drag)

        drag_area = ttk.Frame(title_bar, style="App.TFrame")
        drag_area.pack(side="left", fill="both", expand=True)
        drag_area.bind("<ButtonPress-1>", self._start_window_drag)

        window_controls = ttk.Frame(title_bar, style="App.TFrame")
        window_controls.pack(side="right")
        self.minimize_button = self._create_button(
            window_controls,
            text="—",
            command=self._minimize_window,
            width=2,
            height=26,
            background_role="background",
        )
        self.minimize_button.pack(side="left", padx=2)
        self.maximize_button = self._create_button(
            window_controls,
            text="□",
            command=self._toggle_maximize,
            width=2,
            height=26,
            background_role="background",
        )
        self.maximize_button.pack(side="left", padx=2)
        self.close_button = self._create_button(
            window_controls,
            text="×",
            command=self._close_window,
            variant="danger",
            width=2,
            height=26,
            background_role="background",
        )
        self.close_button.pack(side="left", padx=2)

        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(6, weight=1)

        header = ttk.Frame(frame, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(1, weight=1)
        url_bar = ttk.Frame(header, style="Panel.TFrame", padding=6)
        url_bar.grid(row=0, column=1, rowspan=2, sticky="ew", padx=8)
        url_bar.columnconfigure(0, weight=1)
        self.url_entry = RoundedEntry(url_bar, textvariable=self.url, palette=self.palette)
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(2, 6))
        self.paste_button = self._create_button(
            url_bar,
            text="Pegar enlace",
            command=self._paste_url,
            background_role="surface",
        )
        self.paste_button.grid(row=0, column=1, padx=3, ipady=2)
        self.analyze_button = self._create_button(
            url_bar,
            text="Analizar playlist",
            command=self._start_metadata_lookup,
            variant="primary",
            background_role="surface",
        )
        self.analyze_button.grid(row=0, column=2, padx=(3, 2), ipady=2)

        self.engine_status = ttk.Label(
            header,
            text="● Motor yt-dlp listo",
            style="Engine.TLabel",
            padding=(10, 7),
        )
        self.engine_status.grid(row=0, column=2, rowspan=2, padx=(8, 4))
        self.theme_button = self._create_button(
            header,
            text="Tema claro",
            command=self._toggle_theme,
            variant="outline",
        )
        self.theme_button.grid(row=0, column=3, rowspan=2, sticky="e", padx=(0, 6))

        mode_frame = ttk.Frame(frame, style="App.TFrame")
        mode_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            mode_frame, text="MODO:", style="Muted.TLabel", font=("Segoe UI", 8, "bold")
        ).pack(side="left", padx=(4, 8))
        self.single_radio = ttk.Radiobutton(
            mode_frame,
            text="Canción individual",
            variable=self.download_mode,
            value="single",
            command=self._on_mode_changed,
        )
        self.single_radio.pack(side="left", padx=(0, 12))
        self.playlist_radio = ttk.Radiobutton(
            mode_frame,
            text="Playlist completa",
            variable=self.download_mode,
            value="playlist",
            command=self._on_mode_changed,
        )
        self.playlist_radio.pack(side="left")
        self.search_radio = ttk.Radiobutton(
            mode_frame,
            text="Buscar en YouTube",
            variable=self.download_mode,
            value="search",
            command=self._on_mode_changed,
        )
        self.search_radio.pack(side="left", padx=(12, 0))

        self.summary_card = ttk.Frame(frame, style="Panel.TFrame", padding=12)
        self.summary_card.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.summary_card.columnconfigure(2, weight=1)
        self.playlist_cover = ttk.Label(
            self.summary_card,
            text="♫",
            anchor="center",
            style="Cover.TLabel",
            width=10,
        )
        self.playlist_cover.grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="ns")
        self.playlist_badge = ttk.Label(
            self.summary_card,
            text="ENLACE PENDIENTE",
            style="Badge.TLabel",
            padding=(7, 3),
        )
        self.playlist_badge.grid(row=0, column=1, sticky="w")
        self.playlist_title_label = ttk.Label(
            self.summary_card,
            text="Tu playlist aparecerá aquí",
            style="SummaryTitle.TLabel",
            font=("Segoe UI", 15, "bold"),
            wraplength=440,
        )
        self.playlist_title_label.grid(row=1, column=1, sticky="nw", pady=(5, 0))
        self.playlist_stats = ttk.Label(
            self.summary_card,
            text="0 canciones · Lista para analizar",
            style="PanelMuted.TLabel",
        )
        self.playlist_stats.grid(row=2, column=1, sticky="w", pady=(7, 0))

        summary_actions = ttk.Frame(self.summary_card, style="Panel.TFrame")
        summary_actions.grid(row=0, column=3, rowspan=3, sticky="e", padx=(10, 0))
        self.download_all_button = self._create_button(
            summary_actions,
            text="Descargar todo en MP3",
            command=self._start_download_all,
            variant="primary",
            background_role="surface",
        )
        self.download_all_button.pack(fill="x", pady=(0, 5), ipady=2)
        self.clip_editor_button = self._create_button(
            summary_actions,
            text="Editar fragmento",
            command=self._open_clip_editor,
            state="disabled",
            background_role="surface",
        )
        self.clip_editor_button.pack(fill="x", pady=(0, 5), ipady=2)
        self.search_queue_button = self._create_button(
            summary_actions,
            text="Ver cola (0)",
            command=self._toggle_search_queue_view,
            background_role="surface",
        )
        self.search_queue_button.pack(fill="x", pady=(0, 5), ipady=2)
        self.search_queue_button.pack_forget()
        self.pause_all_button = self._create_button(
            summary_actions,
            text="Ⅱ  Pausar todo",
            state="disabled",
            background_role="surface",
        )
        self.pause_all_button.pack(fill="x", pady=2, ipady=2)
        self.clear_completed_button = self._create_button(
            summary_actions,
            text="Limpiar completados",
            state="disabled",
            background_role="surface",
        )
        self.clear_completed_button.pack(fill="x", pady=(2, 0), ipady=2)

        settings_panel = ttk.Frame(frame, style="Panel.TFrame", padding=9)
        settings_panel.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        settings_panel.columnconfigure(4, weight=1)
        ttk.Label(
            settings_panel,
            text="♫  CALIDAD MP3",
            foreground=self.palette["danger"],
            style="Panel.TLabel",
            font=("Segoe UI", 8, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.quality_value = tk.StringVar(value="192 kbps (Estándar)")
        self.quality_combo = ttk.Combobox(
            settings_panel,
            textvariable=self.quality_value,
            values=("320 kbps (Máxima)", "256 kbps (Alta)", "192 kbps (Estándar)", "V0 VBR"),
            state="disabled",
            width=22,
        )
        self.quality_combo.grid(row=0, column=1, sticky="w")
        self.embed_metadata = tk.BooleanVar(value=True)
        self.embed_checkbox = ttk.Checkbutton(
            settings_panel,
            text="Incrustar carátula y metadatos",
            variable=self.embed_metadata,
            style="Panel.TCheckbutton",
        )
        self.embed_checkbox.grid(row=0, column=3, sticky="w", padx=(12, 8))
        self.normalize_audio = tk.BooleanVar(value=False)
        self.normalize_checkbox = ttk.Checkbutton(
            settings_panel,
            text="Normalizar volumen",
            variable=self.normalize_audio,
            state="disabled",
            style="Panel.TCheckbutton",
        )
        self.normalize_checkbox.grid(row=0, column=4, sticky="e")

        destination = ttk.Frame(frame, style="Panel.TFrame", padding=8)
        destination.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            destination, text="▣  Carpeta de destino:", style="PanelMuted.TLabel"
        ).pack(side="left", padx=(2, 8))
        self.destination_label = ttk.Label(
            destination,
            textvariable=self.output_directory,
            style="Path.TLabel",
            padding=(6, 3),
        )
        self.destination_label.pack(side="left", fill="x", expand=True)
        self.folder_button = self._create_button(
            destination,
            text="Cambiar carpeta",
            command=self._choose_folder,
            background_role="surface",
        )
        self.folder_button.pack(side="right", padx=(8, 0), ipady=2)

        queue_panel = ttk.Frame(frame, style="Panel.TFrame")
        queue_panel.grid(row=5, column=0, rowspan=2, sticky="nsew", pady=(0, 8))
        queue_panel.columnconfigure(0, weight=1)
        queue_panel.rowconfigure(1, weight=1)
        headings = ttk.Frame(queue_panel, style="TableHeader.TFrame", padding=(8, 7))
        self.queue_headings = headings
        headings.grid(row=0, column=0, sticky="ew")
        for column, weight, minsize in (
            (0, 0, 36), (1, 0, 42), (2, 3, 304), (3, 0, 70),
            (4, 0, 80), (5, 3, 180), (6, 0, 120), (7, 0, 90),
        ):
            headings.columnconfigure(column, weight=weight, minsize=minsize)
        self.select_all = tk.BooleanVar(value=True)
        self.select_all_checkbox = ttk.Checkbutton(
            headings,
            variable=self.select_all,
            command=self._set_all_selected,
            style="Panel.TCheckbutton",
        )
        self.select_all_checkbox.grid(row=0, column=0, sticky="w")
        for column, text in enumerate(
            ("#", "MINIATURA Y PISTA", "DURACIÓN", "CALIDAD", "PROGRESO INDIVIDUAL", "VELOCIDAD / PESO", "ACCIONES"),
            start=1,
        ):
            ttk.Label(
                headings,
                text=text,
                style="TableHeading.TLabel",
                font=("Segoe UI", 8, "bold"),
            ).grid(row=0, column=column, sticky="w", padx=4)

        self.canvas = tk.Canvas(
            queue_panel,
            background=self.palette["background"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.scrollbar = SubtleScrollbar(
            queue_panel,
            command=self.canvas.yview,
            palette=self.palette,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.scrollbar.grid(row=1, column=1, sticky="ns", padx=(2, 5), pady=5)

        self.items_frame = ttk.Frame(self.canvas, style="Panel.TFrame")
        self.items_frame.columnconfigure(0, weight=1)
        self.items_window = self.canvas.create_window(
            (0, 0), window=self.items_frame, anchor="nw"
        )
        self.items_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_items_frame)
        self.canvas.bind("<Configure>", self._position_empty_state, add="+")
        self.empty_state = self.canvas.create_text(
            0,
            0,
            text="Tus canciones aparecerán aquí\nPega un enlace y obtén la información para empezar.",
            fill=self.palette["muted"],
            font=("Segoe UI", 12),
            justify="center",
            width=440,
            tags=("empty-state",),
        )

        footer = ttk.Frame(frame, style="App.TFrame", padding=(2, 6))
        footer.grid(row=7, column=0, sticky="ew")
        footer.columnconfigure(1, weight=1)
        self.queue_status_icon = ttk.Label(
            footer, text="↻", style="QueueIcon.TLabel", font=("Segoe UI", 18, "bold")
        )
        self.queue_status_icon.grid(row=0, column=0, rowspan=2, padx=(0, 9))
        self.status_label = ttk.Label(
            footer, textvariable=self.status, style="FooterTitle.TLabel"
        )
        self.status_label.grid(row=0, column=1, sticky="w")
        self.progress_summary = ttk.Label(
            footer,
            text="0 de 0 canciones",
            style="Muted.TLabel",
            font=("Segoe UI", 8),
        )
        self.progress_summary.grid(row=1, column=1, sticky="w")
        self.overall_progress = ttk.Progressbar(
            footer, mode="determinate", maximum=100, length=150
        )
        self.overall_progress.grid(row=0, column=2, rowspan=2, padx=12, sticky="ew")
        self.details_button = self._create_button(
            footer,
            text="Mostrar detalles",
            command=self._toggle_details,
            variant="outline",
        )
        self.details_button.grid(row=0, column=3, rowspan=2, padx=(4, 8))
        self.pause_queue_button = self._create_button(
            footer, text="Ⅱ  Pausar", state="disabled"
        )
        self.pause_queue_button.grid(row=0, column=4, rowspan=2, padx=4, ipady=2)
        self.cancel_queue_button = self._create_button(
            footer, text="⊗  Cancelar cola", state="disabled"
        )
        self.cancel_queue_button.grid(row=0, column=5, rowspan=2, padx=(4, 0), ipady=2)

        self.loading_bar = ttk.Progressbar(frame, mode="indeterminate")
        self.loading_bar.grid(row=8, column=0, sticky="ew", pady=(0, 6))
        self.loading_bar.grid_remove()

        self.details_frame = ttk.LabelFrame(
            frame, text="Detalles técnicos", padding=6, style="TLabelframe"
        )
        self.log = tk.Text(
            self.details_frame, height=7, state="disabled", wrap="word"
        )
        self.log.pack(fill="both", expand=True)

        self.bottom_action_button = self._create_button(
            footer,
            text="Descargar selección (0 pistas MP3)",
            command=self._start_download,
            variant="primary",
        )
        self.bottom_action_button.grid(row=0, column=6, rowspan=2, padx=(8, 0), ipady=2)

        self.search_page = ttk.Frame(
            self.root,
            style="App.TFrame",
            padding=(18, 14),
        )
        self.search_page.columnconfigure(0, weight=3, minsize=600)
        self.search_page.columnconfigure(1, weight=1, minsize=205)
        self.search_page.rowconfigure(3, weight=1)
        self.search_page.place(
            x=0,
            y=38,
            relwidth=1,
            relheight=1,
            height=-38,
        )
        self.search_page.place_forget()

        search_header = ttk.Frame(self.search_page, style="App.TFrame")
        search_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        search_header.columnconfigure(1, weight=1)
        ttk.Label(
            search_header,
            text="YouTube",
            style="SearchPageTitle.TLabel",
            font=("Segoe UI", 20, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            search_header,
            text="BUSCADOR DE MÚSICA",
            style="Muted.TLabel",
            font=("Segoe UI", 8, "bold"),
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        search_navigation = ttk.Frame(search_header, style="App.TFrame")
        search_navigation.grid(row=0, column=2, rowspan=2, sticky="e")
        self.search_single_button = self._create_button(
            search_navigation,
            text="Canción",
            command=lambda: self._select_download_mode("single"),
        )
        self.search_single_button.pack(side="left", padx=(0, 6))
        self.search_playlist_button = self._create_button(
            search_navigation,
            text="Playlist",
            command=lambda: self._select_download_mode("playlist"),
        )
        self.search_playlist_button.pack(side="left", padx=(0, 10))
        self.search_queue_page_button = self._create_button(
            search_navigation,
            text="Ver cola (0)",
            command=self._toggle_search_queue_view,
            variant="primary",
        )
        self.search_queue_page_button.pack(side="left")

        search_bar = ttk.Frame(self.search_page, style="Panel.TFrame", padding=8)
        search_bar.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        search_bar.columnconfigure(0, weight=1)
        self.search_entry = RoundedEntry(
            search_bar,
            textvariable=self.search_query,
            palette=self.palette,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(2, 8))
        self.search_entry.entry.bind(
            "<Return>", lambda _event: self._start_search_from_page()
        )
        self.search_page_button = self._create_button(
            search_bar,
            text="Buscar",
            command=self._start_search_from_page,
            variant="primary",
            background_role="surface",
        )
        self.search_page_button.grid(row=0, column=1, ipady=3)

        self.search_results_heading = ttk.Label(
            self.search_page,
            text="Busca canciones, artistas o videos",
            style="SearchPageTitle.TLabel",
            font=("Segoe UI", 13, "bold"),
        )
        self.search_results_heading.grid(row=2, column=0, sticky="w", pady=(4, 10))
        search_results_panel = ttk.Frame(
            self.search_page,
            style="Panel.TFrame",
        )
        search_results_panel.grid(row=3, column=0, sticky="nsew")
        search_results_panel.columnconfigure(0, weight=1)
        search_results_panel.rowconfigure(0, weight=1)
        self.search_canvas = tk.Canvas(
            search_results_panel,
            background=self.palette["surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.search_scrollbar = SubtleScrollbar(
            search_results_panel,
            command=self.search_canvas.yview,
            palette=self.palette,
        )
        self.search_canvas.configure(yscrollcommand=self.search_scrollbar.set)
        self.search_canvas.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        self.search_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=8)
        self.search_results_frame = ttk.Frame(
            self.search_canvas,
            style="Panel.TFrame",
        )
        self.search_results_frame.columnconfigure(0, weight=1)
        self.search_results_window = self.search_canvas.create_window(
            (0, 0),
            window=self.search_results_frame,
            anchor="nw",
        )
        self.search_results_frame.bind(
            "<Configure>",
            lambda _event: self.search_canvas.configure(
                scrollregion=self.search_canvas.bbox("all")
            ),
        )
        self.search_canvas.bind(
            "<Configure>",
            lambda event: self.search_canvas.itemconfigure(
                self.search_results_window,
                width=event.width,
            ),
        )
        self.search_empty_state = ttk.Label(
            self.search_results_frame,
            text="Escribe una búsqueda arriba para encontrar videos.",
            style="PanelMuted.TLabel",
            font=("Segoe UI", 11),
            anchor="center",
            padding=24,
        )
        self.search_empty_state.grid(row=0, column=0, sticky="ew")

        search_queue_panel = ttk.Frame(
            self.search_page,
            style="Panel.TFrame",
            padding=10,
        )
        search_queue_panel.grid(
            row=2,
            column=1,
            rowspan=2,
            sticky="nsew",
            padx=(12, 0),
            pady=(4, 0),
        )
        search_queue_panel.columnconfigure(0, weight=1)
        search_queue_panel.rowconfigure(2, weight=1)
        ttk.Label(
            search_queue_panel,
            text="Tu lista",
            style="Panel.TLabel",
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self.search_queue_count_label = ttk.Label(
            search_queue_panel,
            text="0 videos añadidos",
            style="PanelMuted.TLabel",
            font=("Segoe UI", 8),
        )
        self.search_queue_count_label.grid(
            row=1, column=0, sticky="w", pady=(2, 8)
        )
        self.search_queue_canvas = tk.Canvas(
            search_queue_panel,
            background=self.palette["surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.search_queue_scrollbar = SubtleScrollbar(
            search_queue_panel,
            command=self.search_queue_canvas.yview,
            palette=self.palette,
        )
        self.search_queue_canvas.configure(
            yscrollcommand=self.search_queue_scrollbar.set
        )
        self.search_queue_canvas.grid(row=2, column=0, sticky="nsew")
        self.search_queue_scrollbar.grid(
            row=2, column=1, sticky="ns", padx=(3, 0)
        )
        self.search_queue_frame = ttk.Frame(
            self.search_queue_canvas,
            style="Panel.TFrame",
        )
        self.search_queue_frame.columnconfigure(0, weight=1)
        self.search_queue_window = self.search_queue_canvas.create_window(
            (0, 0),
            window=self.search_queue_frame,
            anchor="nw",
        )
        self.search_queue_frame.bind(
            "<Configure>",
            lambda _event: self.search_queue_canvas.configure(
                scrollregion=self.search_queue_canvas.bbox("all")
            ),
        )
        self.search_queue_canvas.bind(
            "<Configure>",
            lambda event: self.search_queue_canvas.itemconfigure(
                self.search_queue_window,
                width=event.width,
            ),
        )
        self.search_queue_empty_label = ttk.Label(
            self.search_queue_frame,
            text="Añade videos desde los resultados.",
            style="PanelMuted.TLabel",
            font=("Segoe UI", 9),
            wraplength=150,
            justify="left",
            padding=(2, 10),
        )
        self.search_queue_empty_label.grid(row=0, column=0, sticky="ew")
        self.search_queue_download_button = self._create_button(
            search_queue_panel,
            text="Revisar y descargar",
            command=self._toggle_search_queue_view,
            variant="primary",
            background_role="surface",
        )
        self.search_queue_download_button.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0), ipady=3
        )
        self._refresh_search_queue_sidebar()
        self.root.bind_all("<MouseWheel>", self._scroll_under_pointer)
        self.root.bind_all("<Button-4>", self._scroll_under_pointer)
        self.root.bind_all("<Button-5>", self._scroll_under_pointer)

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _position_empty_state(self, event: tk.Event) -> None:
        self.canvas.coords(self.empty_state, event.width / 2, event.height / 2)

    def _update_empty_state(self) -> None:
        if not hasattr(self, "canvas"):
            return
        if self.download_mode.get() == "search":
            if self._search_view == "queue":
                empty_text = "Tu cola está vacía\nBusca videos y añádelos para descargarlos."
            elif self._search_query:
                empty_text = "No se encontraron videos.\nPrueba con otros términos de búsqueda."
            else:
                empty_text = "Busca canciones, artistas o videos de YouTube."
        else:
            empty_text = (
                "Tus canciones aparecerán aquí\n"
                "Pega un enlace y obtén la información para empezar."
            )
        self.canvas.itemconfigure(
            self.empty_state,
            text=empty_text,
            state="hidden" if self.items else "normal",
            fill=self.palette["muted"],
        )

    def _resize_items_frame(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.items_window, width=event.width)

    def _scroll_under_pointer(self, event: tk.Event) -> str | None:
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return None
        scrollbars = {
            self.scrollbar: self.canvas,
            self.search_scrollbar: self.search_canvas,
            self.search_queue_scrollbar: self.search_queue_canvas,
        }
        canvases = {
            self.canvas,
            self.search_canvas,
            self.search_queue_canvas,
        }
        while widget is not None:
            if widget in scrollbars:
                canvas = scrollbars[widget]
                break
            if widget in canvases:
                canvas = widget
                break
            widget = getattr(widget, "master", None)
        else:
            return None

        if not canvas.winfo_exists():
            return None
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = event.delta
            units = -int(delta / 120)
            if units == 0 and delta:
                units = -1 if delta > 0 else 1
        if units:
            canvas.yview_scroll(units, "units")
        return "break"

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(
            initialdir=self.output_directory.get(), title="Elegir carpeta de destino"
        )
        if folder:
            self.output_directory.set(folder)

    def _paste_url(self) -> None:
        try:
            clipboard = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showerror("Portapapeles vacío", "No hay un enlace de texto para pegar.")
            return
        self.url.set(clipboard.strip())
        self.url_entry.focus_set()

    def _set_all_selected(self) -> None:
        selected = self.select_all.get()
        for widgets in self.item_widgets:
            widgets["selected"].set(selected)
        self._update_selection_count()

    def _update_selection_count(self) -> None:
        selected_count = sum(
            bool(widgets["selected"].get()) for widgets in self.item_widgets
        )
        selected_noun = "pista" if selected_count == 1 else "pistas"
        total_noun = "pista" if len(self.items) == 1 else "pistas"
        self.bottom_action_button.configure(
            text=f"Descargar selección ({selected_count} {selected_noun} MP3)"
        )
        self.download_all_button.configure(
            text=f"Descargar todo en MP3 ({len(self.items)} {total_noun})"
        )
        self.select_all.set(
            bool(self.item_widgets) and selected_count == len(self.item_widgets)
        )

    def _set_action_text(self, text: str) -> None:
        self.download_all_button.configure(text=text)
        self.bottom_action_button.configure(text=text)

    def _on_url_changed(self, *_args: object) -> None:
        if not self.downloading:
            self._reset_metadata()

    def _reset_metadata(self) -> None:
        if self.downloading:
            return
        self._close_clip_editor()
        self.metadata_ready = False
        self.clip_section = None
        self.search_results = []
        if self.download_mode.get() == "search":
            self._search_view = "results"
            self._search_query = ""
            self._show_search_result_cards([])
        self.items = []
        self.item_widgets.clear()
        if self.download_mode.get() == "search":
            self.queue_headings.grid_remove()
        else:
            self.queue_headings.grid()
        for child in self.items_frame.winfo_children():
            child.destroy()
        self._update_empty_state()
        self._set_action_text("Descargar todo en MP3")
        self.playlist_title_label.configure(text="Tu playlist aparecerá aquí")
        self.playlist_badge.configure(text="ENLACE PENDIENTE")
        self.playlist_stats.configure(text="0 canciones · Lista para analizar")
        self.playlist_cover.configure(image="", text="♫")
        self.playlist_cover.image = None
        self._update_selection_count()
        self.download_all_button.configure(state="disabled")
        self.bottom_action_button.configure(state="disabled")
        self.analyze_button.configure(
            text="Buscar videos" if self.download_mode.get() == "search"
            else "Analizar playlist",
            state="normal",
        )
        self._update_clip_editor_button()
        self.status.set("Pega un enlace para comenzar.")
        self.canvas.yview_moveto(0)

    def _show_items(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.item_widgets.clear()
        search_results_view = (
            self.download_mode.get() == "search" and self._search_view == "results"
        )
        search_queue_view = (
            self.download_mode.get() == "search" and self._search_view == "queue"
        )
        if search_results_view:
            self.queue_headings.grid_remove()
        else:
            self.queue_headings.grid()
        self._update_empty_state()
        for child in self.items_frame.winfo_children():
            child.destroy()
        self._prune_destroyed_buttons()

        if search_results_view:
            self._show_search_result_cards(items)
            self.search_canvas.yview_moveto(0)
            return

        for index, item in enumerate(items):
            row = ttk.Frame(
                self.items_frame,
                style="QueueRow.TFrame",
                padding=(8, 7),
            )
            row.grid(row=index, column=0, sticky="ew")
            for column, weight, minsize in (
                (0, 0, 36), (1, 0, 42), (2, 3, 304), (3, 0, 70),
                (4, 0, 80), (5, 3, 180), (6, 0, 120), (7, 0, 90),
            ):
                row.columnconfigure(column, weight=weight, minsize=minsize)

            selected = tk.BooleanVar(value=True)
            checkbox = ttk.Checkbutton(
                row,
                variable=selected,
                command=self._update_selection_count,
                style="Panel.TCheckbutton",
            )
            checkbox.grid(row=0, column=0, sticky="w")
            number = ttk.Label(
                row, text=f"{index + 1:02d}", style="PanelMuted.TLabel"
            )
            number.grid(row=0, column=1, sticky="w", padx=4)

            song = ttk.Frame(row, style="Panel.TFrame")
            song.grid(row=0, column=2, sticky="ew", padx=4)
            song.columnconfigure(1, weight=1)
            cover = ttk.Label(
                song, text="♫", anchor="center", width=7, style="Cover.TLabel"
            )
            cover.grid(row=0, column=0, rowspan=2, padx=(0, 8))
            title = ttk.Label(
                song,
                text=item["title"],
                style="Panel.TLabel",
                font=("Segoe UI", 9, "bold"),
                width=22,
                wraplength=160,
            )
            title.grid(row=0, column=1, sticky="sw")
            artist = ttk.Label(
                song,
                text=item.get("artist") or "Audio",
                style="PanelMuted.TLabel",
                font=("Segoe UI", 8),
                width=22,
                wraplength=160,
            )
            artist.grid(row=1, column=1, sticky="nw")

            duration = ttk.Label(
                row,
                text=self._format_duration(item["duration"]),
                style="Panel.TLabel",
                font=("Segoe UI", 8),
            )
            duration.grid(row=0, column=3, sticky="w", padx=5)
            quality = ttk.Label(
                row,
                text="MP3\n192k",
                style="Quality.TLabel",
                anchor="center",
                padding=(5, 3),
                font=("Segoe UI", 8, "bold"),
            )
            quality.grid(row=0, column=4, sticky="w", padx=5)

            progress_cell = ttk.Frame(row, style="Panel.TFrame")
            progress_cell.grid(row=0, column=5, sticky="ew", padx=5)
            progress_cell.columnconfigure(0, weight=1)
            item_status = ttk.Label(
                progress_cell,
                text="● En cola",
                style="QueueStatus.TLabel",
                font=("Segoe UI", 8),
            )
            item_status.grid(row=0, column=0, sticky="w", pady=(0, 4))
            percentage = ttk.Label(
                progress_cell, text="0%", style="PanelMuted.TLabel", font=("Segoe UI", 8)
            )
            percentage.grid(row=0, column=1, sticky="e", pady=(0, 4))
            progress = ttk.Progressbar(
                progress_cell, mode="determinate", maximum=100, style="Queue.Horizontal.TProgressbar"
            )
            progress.grid(row=1, column=0, columnspan=2, sticky="ew")

            speed = ttk.Label(
                row,
                text="-- MB/s\nEn espera",
                style="PanelMuted.TLabel",
                font=("Segoe UI", 8),
                justify="center",
            )
            speed.grid(row=0, column=6, sticky="ew", padx=4)
            actions = ttk.Frame(row, style="Panel.TFrame")
            actions.grid(row=0, column=7, sticky="e", padx=(2, 0))
            pause = self._create_button(
                actions,
                text="Ⅱ",
                width=2,
                height=30,
                state="disabled",
                background_role="surface",
            )
            pause.pack(side="left", padx=1)
            cancel = self._create_button(
                actions,
                text="×",
                width=2,
                height=30,
                state="normal" if search_queue_view else "disabled",
                command=(
                    lambda item_index=index: self._remove_search_queue_item(
                        item_index
                    )
                ) if search_queue_view else None,
                background_role="surface",
            )
            cancel.pack(side="left", padx=1)
            show_location = self._create_button(
                actions,
                text="📂",
                width=2,
                height=30,
                state="disabled",
                command=lambda item_index=index: self._open_download_location(
                    item_index
                ),
                background_role="surface",
            )
            show_location.pack(side="left", padx=1)
            item_widget = {
                "card": row,
                "cover": cover,
                "progress": progress,
                "status": item_status,
                "percentage": percentage,
                "speed": speed,
                "selected": selected,
                "checkbox": checkbox,
                "image": None,
                "output_path": None,
            }
            item_widget["show_location"] = show_location
            self.item_widgets.append(item_widget)
            if item.get("_thumbnail_data"):
                self._set_thumbnail(index, item["_thumbnail_data"])
        self.select_all.set(bool(items))
        self.select_all_checkbox.configure(
            state="disabled" if search_results_view else "normal"
        )
        self._update_selection_count()
        self.canvas.yview_moveto(0)

    def _show_search_result_cards(self, items: list[dict[str, Any]]) -> None:
        for child in self.search_results_frame.winfo_children():
            child.destroy()
        self._prune_destroyed_buttons()
        self.item_widgets.clear()
        for column in range(3):
            self.search_results_frame.columnconfigure(column, weight=1, uniform="search")
        if not items:
            self.search_empty_state = ttk.Label(
                self.search_results_frame,
                text="No se encontraron videos. Prueba con otra búsqueda.",
                style="PanelMuted.TLabel",
                font=("Segoe UI", 11),
                anchor="center",
                padding=24,
            )
            self.search_empty_state.grid(row=0, column=0, sticky="ew")
            return

        for index, item in enumerate(items):
            card = ttk.Frame(
                self.search_results_frame,
                style="QueueRow.TFrame",
                padding=8,
            )
            card.grid(
                row=index // 3,
                column=index % 3,
                sticky="nsew",
                pady=4,
                padx=4,
            )
            card.columnconfigure(0, weight=1)

            cover_frame = ttk.Frame(
                card,
                width=160,
                height=90,
                style="QueueRow.TFrame",
            )
            cover_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            cover_frame.grid_propagate(False)
            cover = ttk.Label(
                cover_frame,
                text="▶",
                anchor="center",
                style="Cover.TLabel",
            )
            cover.pack(fill="both", expand=True)

            title = ttk.Label(
                card,
                text=item["title"],
                style="Panel.TLabel",
                font=("Segoe UI", 9, "bold"),
                wraplength=160,
                justify="left",
            )
            title.grid(row=1, column=0, sticky="nw", pady=(0, 5))
            channel = ttk.Label(
                card,
                text=item.get("artist") or "Canal desconocido",
                style="PanelMuted.TLabel",
                font=("Segoe UI", 8),
                wraplength=160,
            )
            channel.grid(row=2, column=0, sticky="nw", pady=(0, 3))
            duration = ttk.Label(
                card,
                text=f"Duración: {self._format_duration(item.get('duration'))}",
                style="PanelMuted.TLabel",
                font=("Segoe UI", 8),
            )
            duration.grid(row=3, column=0, sticky="nw", pady=(0, 8))

            already_added = any(
                queued.get("url") == item.get("url")
                for queued in self.search_queue
            )
            actions = ttk.Frame(card, style="QueueRow.TFrame")
            actions.grid(row=4, column=0, sticky="e")
            play_button = self._create_button(
                actions,
                text="▶",
                command=lambda item_index=index: self._open_search_preview(
                    item_index
                ),
                variant="primary",
                background_role="surface",
                width=3,
                height=30,
            )
            play_button.pack(side="left", padx=(0, 5))
            add_button = self._create_button(
                actions,
                text="+",
                command=lambda item_index=index: self._add_search_result(item_index),
                variant="primary",
                state="disabled" if already_added else "normal",
                background_role="surface",
                width=3,
                height=30,
            )
            add_button.pack(side="left")

            selected = tk.BooleanVar(value=False)
            checkbox = ttk.Checkbutton(
                card,
                variable=selected,
                style="Panel.TCheckbutton",
                state="disabled",
            )
            self.item_widgets.append(
                {
                    "card": card,
                    "cover": cover,
                    "image": None,
                    "selected": selected,
                    "checkbox": checkbox,
                    "add_button": add_button,
                    "play_button": play_button,
                    "thumbnail_size": (160, 90),
                }
            )
            if item.get("_thumbnail_data"):
                self._set_thumbnail(index, item["_thumbnail_data"])
        self.select_all.set(False)
        self._update_selection_count()

    def _refresh_search_queue_sidebar(self) -> None:
        if not hasattr(self, "search_queue_frame"):
            return
        for child in self.search_queue_frame.winfo_children():
            child.destroy()
        count = len(self.search_queue)
        noun = "video añadido" if count == 1 else "videos añadidos"
        self.search_queue_count_label.configure(text=f"{count} {noun}")
        self.search_queue_download_button.configure(
            text="Revisar y descargar" if count else "La lista está vacía",
            state="normal" if count else "disabled",
        )
        if not count:
            self.search_queue_empty_label = ttk.Label(
                self.search_queue_frame,
                text="Añade videos desde los resultados.",
                style="PanelMuted.TLabel",
                font=("Segoe UI", 9),
                wraplength=150,
                justify="left",
                padding=(2, 10),
            )
            self.search_queue_empty_label.grid(row=0, column=0, sticky="ew")
        for index, item in enumerate(self.search_queue):
            row = ttk.Frame(
                self.search_queue_frame,
                style="QueueRow.TFrame",
                padding=(6, 5),
            )
            row.grid(row=index, column=0, sticky="ew", pady=(0, 5))
            row.columnconfigure(0, weight=1)
            title = ttk.Label(
                row,
                text=item["title"],
                style="Panel.TLabel",
                font=("Segoe UI", 8, "bold"),
                wraplength=140,
                justify="left",
            )
            title.grid(row=0, column=0, sticky="ew", padx=(0, 4))
            remove_button = ttk.Button(
                row,
                text="×",
                command=lambda item_index=index: self._remove_search_queue_sidebar_item(item_index),
                style="Icon.TButton",
            )
            remove_button.grid(row=0, column=1, sticky="ne")

    def _prune_destroyed_buttons(self) -> None:
        self.rounded_buttons = [
            button for button in self.rounded_buttons if button.winfo_exists()
        ]

    def _open_download_location(self, index: int) -> None:
        """Open Explorer with the completed audio file selected."""
        if not 0 <= index < len(self.item_widgets):
            return
        output_path = self.item_widgets[index].get("output_path")
        if not output_path:
            messagebox.showinfo(
                "Archivo no disponible",
                "La ubicación estará disponible cuando termine la conversión.",
            )
            return

        path = Path(output_path)
        if not path.is_file():
            messagebox.showerror(
                "Archivo no encontrado",
                f"No se encontró el archivo descargado:\n{path}",
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(path.parent, "open")
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except OSError as error:
            messagebox.showerror(
                "No se pudo abrir la carpeta",
                f"No se pudo mostrar la ubicación del archivo.\n\n{error}",
            )

    @staticmethod
    def _format_duration(value: object) -> str:
        if not isinstance(value, (int, float)):
            return "Desconocida"
        seconds = int(value)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @staticmethod
    def _format_speed(value: float) -> str:
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f} MB/s"
        if value >= 1_000:
            return f"{value / 1_000:.0f} KB/s"
        return f"{value:.0f} B/s"

    def _set_thumbnail(self, index: int, image_data: bytes) -> None:
        try:
            photo = create_thumbnail(
                image_data,
                self.item_widgets[index].get("thumbnail_size", (72, 44)),
            )
            if 0 <= index < len(self.items):
                self.items[index]["_thumbnail_data"] = image_data
            cover = self.item_widgets[index]["cover"]
            cover.configure(image=photo, text="")
            self.item_widgets[index]["image"] = photo
        except (IndexError, OSError, tk.TclError) as error:
            self._append_log(f"No se pudo mostrar una portada: {error}")

    def _set_playlist_cover(self, image_data: bytes) -> None:
        try:
            photo = create_thumbnail(image_data, (100, 76))
            self.playlist_cover.configure(image=photo, text="")
            self.playlist_cover.image = photo
        except (OSError, tk.TclError) as error:
            self._append_log(f"No se pudo mostrar la portada de la playlist: {error}")

    def _toggle_details(self) -> None:
        if self.details_visible:
            self.details_frame.grid_remove()
            self.details_button.set_text("Mostrar detalles")
        else:
            self.details_frame.grid(
                row=9, column=0, sticky="nsew", pady=(4, 8)
            )
            self.details_button.set_text("Ocultar detalles")
        self.details_visible = not self.details_visible

    def _set_loading(self, active: bool) -> None:
        self._loading = active
        if active:
            self.loading_bar.grid()
            self.loading_bar.start(12)
        else:
            self.loading_bar.stop()
            self.loading_bar.grid_remove()

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.url_entry.configure(state=state)
        self.paste_button.configure(state=state)
        analyze_text = (
            "Buscar videos"
            if self.download_mode.get() == "search"
            else "Analizar playlist"
        )
        self.analyze_button.configure(state=state, text=analyze_text)
        self.folder_button.configure(state=state)
        self.single_radio.configure(state=state)
        self.playlist_radio.configure(state=state)
        self.search_radio.configure(state=state)
        self.download_all_button.configure(state=state)
        self.bottom_action_button.configure(state=state)
        if not enabled:
            self.clip_editor_button.configure(state="disabled")
        else:
            self._update_clip_editor_button()
        self.select_all_checkbox.configure(state=state)
        self.embed_checkbox.configure(state=state)
        self.search_entry.configure(state=state)
        self.search_page_button.configure(state=state)
        self.search_single_button.configure(state=state)
        self.search_playlist_button.configure(state=state)
        self._update_search_queue_button()
        for widgets in self.item_widgets:
            widgets["checkbox"].configure(state=state)
