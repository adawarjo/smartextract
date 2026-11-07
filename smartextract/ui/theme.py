# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Warna, font, dan ikon aplikasi. Warna ditulis sebagai (mode terang, mode gelap)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

BG = ("#F3F5F9", "#0D1220")
SURFACE = ("#FFFFFF", "#161D2E")
SURFACE_ALT = ("#F1F4F9", "#1F283B")
BORDER = ("#E2E7EF", "#2A3448")
TEXT = ("#111827", "#EDF1F7")
MUTED = ("#64748B", "#94A3B8")
ACCENT = ("#2563EB", "#3B82F6")
ACCENT_HOVER = ("#1D4ED8", "#2563EB")
ACCENT_SOFT = ("#E4ECFD", "#1C2C4F")
SUCCESS = ("#15803D", "#4ADE80")
WARNING = ("#B45309", "#FBBF24")
DANGER = ("#B91C1C", "#F87171")
DANGER_FILL = ("#DC2626", "#DC2626")
DANGER_HOVER = ("#B91C1C", "#B91C1C")
SIDEBAR = ("#101A36", "#090E1A")
SIDEBAR_ACTIVE = "#233260"
SIDEBAR_HOVER = "#1A2749"
SIDEBAR_TEXT = "#C9D3E8"

ICON_DOCUMENT = "\uE8A5"
ICON_CHANGE = "\uE895"
ICON_INFO = "\uE946"
ICON_CALENDAR = "\uE787"
ICON_FOLDER = "\uE8B7"
ICON_FILES = "\uE8E5"
ICON_PLAY = "\uE768"
ICON_STOP = "\uE711"
ICON_SAVE = "\uE74E"
ICON_EXPORT = "\uE896"
ICON_OPEN = "\uE8A7"
ICON_LOGO = "\uE9D5"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    family = "Segoe UI Semibold" if weight == "semibold" else "Segoe UI"
    return ctk.CTkFont(family=family, size=size, weight="bold" if weight == "bold" else "normal")


@lru_cache(maxsize=64)
def icon(glyph: str, size: int = 16, color: str | tuple[str, str] = "#FFFFFF") -> ctk.CTkImage | None:
    """Ikon dari font Segoe MDL2 bawaan Windows, jadi tidak butuh berkas gambar."""
    path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segmdl2.ttf"
    if not path.exists():
        return None
    light, dark = (color, color) if isinstance(color, str) else color

    def render(fill: str) -> Image.Image:
        canvas = size * 4
        image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        glyph_font = ImageFont.truetype(str(path), int(canvas * 0.86))
        ImageDraw.Draw(image).text((canvas / 2, canvas / 2), glyph, font=glyph_font, fill=fill, anchor="mm")
        return image

    return ctk.CTkImage(light_image=render(light), dark_image=render(dark), size=(size, size))


def pick(color: tuple[str, str]) -> str:
    """Warna untuk mode tampilan yang sedang aktif."""
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


def apply_tree_style(widget) -> None:
    """Treeview bukan bagian CustomTkinter, jadi warnanya diatur lewat ttk."""
    style = ttk.Style(widget)
    style.theme_use("clam")
    scaling = ctk.ScalingTracker.get_window_dpi_scaling(widget.winfo_toplevel())
    surface, text, muted = pick(SURFACE), pick(TEXT), pick(MUTED)

    style.configure(
        "App.Treeview",
        background=surface,
        fieldbackground=surface,
        foreground=text,
        rowheight=int(30 * scaling),
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 10),
    )
    style.configure(
        "App.Treeview.Heading",
        background=pick(SURFACE_ALT),
        foreground=muted,
        borderwidth=0,
        relief="flat",
        padding=(10, 8),
        font=("Segoe UI Semibold", 9),
    )
    style.map("App.Treeview.Heading", background=[("active", pick(SURFACE_ALT))])
    style.map(
        "App.Treeview",
        background=[("selected", pick(ACCENT_SOFT))],
        foreground=[("selected", text)],
    )
    style.layout("App.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
