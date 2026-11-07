# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Jendela utama: sidebar menu dan area halaman."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from .. import __app_name__, __version__
from . import theme
from .pages.about import AboutPage
from .pages.extract_dpa import MENU_PENETAPAN, MENU_PERUBAHAN, ExtractDpaPage
from .pages.extract_rak import MENU_RAK, ExtractRakPage


@dataclass(frozen=True)
class MenuItem:
    key: str
    title: str
    icon: str
    page: Callable


WINDOW_SIZE = (1280, 820)
ICON_PATH = Path(__file__).resolve().parents[1] / "assets" / "icon.ico"

# Menu baru cukup ditambahkan di sini beserta kelas halamannya.
MENUS = (
    MenuItem(
        "extract_dpa",
        MENU_PENETAPAN.title,
        theme.ICON_DOCUMENT,
        partial(ExtractDpaPage, config=MENU_PENETAPAN),
    ),
    MenuItem(
        "extract_dpa_perubahan",
        MENU_PERUBAHAN.title,
        theme.ICON_CHANGE,
        partial(ExtractDpaPage, config=MENU_PERUBAHAN),
    ),
    MenuItem(
        "extract_rak",
        "Extract RAK\nPenetapan/Parsial/Perubahan",
        theme.ICON_CALENDAR,
        partial(ExtractRakPage, config=MENU_RAK),
    ),
    MenuItem("about", "About", theme.ICON_INFO, AboutPage),
)


class SmartExtractApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=theme.BG)
        self.title(__app_name__)
        self.iconbitmap(str(ICON_PATH))
        self.minsize(1000, 620)
        self._fit_to_screen()
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._pages: dict[str, ctk.CTkFrame] = {}
        self._menu_buttons: dict[str, ctk.CTkButton] = {}
        self._active: str | None = None
        theme.apply_tree_style(self)
        self._build_sidebar()
        self.show_page(MENUS[0].key)

    def _fit_to_screen(self) -> None:
        """Jendela tidak boleh melebihi layar; laptop kantor sering hanya 1366x768."""
        scale = ctk.ScalingTracker.get_window_dpi_scaling(self)
        screen_width = int(self.winfo_screenwidth() / scale)
        screen_height = int(self.winfo_screenheight() / scale)
        width = min(WINDOW_SIZE[0], screen_width - 40)
        height = min(WINDOW_SIZE[1], screen_height - 120)
        left = max((screen_width - width) // 2, 0)
        top = max((screen_height - height) // 2 - 24, 0)
        self.geometry(f"{width}x{height}+{left}+{top}")

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=248, corner_radius=0, fg_color=theme.SIDEBAR)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(2, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 26))
        ctk.CTkLabel(
            brand, text="", image=theme.icon(theme.ICON_LOGO, 18), width=36, height=36,
            fg_color=theme.ACCENT[1], corner_radius=10,
        ).pack(side="left")
        ctk.CTkLabel(
            brand, text=__app_name__, font=theme.font(17, "semibold"), text_color="#FFFFFF",
        ).pack(side="left", padx=(12, 0))

        menu = ctk.CTkFrame(sidebar, fg_color="transparent")
        menu.grid(row=1, column=0, sticky="ew", padx=12)
        menu.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            menu, text="MENU", font=theme.font(11, "semibold"), text_color="#7E8CAB", height=20,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(0, 6))
        for index, item in enumerate(MENUS, start=1):
            button = ctk.CTkButton(
                menu,
                text=item.title,
                image=theme.icon(item.icon, 16, theme.SIDEBAR_TEXT),
                compound="left",
                anchor="w",
                height=56 if "\n" in item.title else 42,
                corner_radius=9,
                font=theme.font(13),
                text_color=theme.SIDEBAR_TEXT,
                fg_color="transparent",
                hover_color=theme.SIDEBAR_HOVER,
                command=lambda key=item.key: self.show_page(key),
            )
            if "\n" in item.title:
                button._text_label.configure(justify="left")
            button.grid(row=index, column=0, sticky="ew", pady=2)
            self._menu_buttons[item.key] = button

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=18)
        self._dark_switch = ctk.CTkSwitch(
            footer,
            text="Mode gelap",
            font=theme.font(12),
            text_color=theme.SIDEBAR_TEXT,
            progress_color=theme.ACCENT[1],
            fg_color="#33415F",
            command=self._toggle_theme,
        )
        self._dark_switch.pack(anchor="w")
        ctk.CTkLabel(
            footer, text=f"Versi {__version__}", font=theme.font(11), text_color="#7E8CAB", height=20,
        ).pack(anchor="w", pady=(8, 0))

    def show_page(self, key: str) -> None:
        if key == self._active:
            return
        if self._active:
            self._pages[self._active].grid_remove()
        if key not in self._pages:
            item = next(menu for menu in MENUS if menu.key == key)
            self._pages[key] = item.page(self)
            self._pages[key].grid(row=0, column=1, sticky="nsew")
        else:
            self._pages[key].grid()
        for name, button in self._menu_buttons.items():
            active = name == key
            button.configure(
                fg_color=theme.SIDEBAR_ACTIVE if active else "transparent",
                text_color="#FFFFFF" if active else theme.SIDEBAR_TEXT,
            )
        self._active = key

    def _toggle_theme(self) -> None:
        ctk.set_appearance_mode("dark" if self._dark_switch.get() else "light")
        theme.apply_tree_style(self)
        for page in self._pages.values():
            page.refresh_theme()


def main() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    SmartExtractApp().mainloop()
