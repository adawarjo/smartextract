# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Menu About: identitas aplikasi, disclaimer, dan pemberitahuan lisensi."""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

import customtkinter as ctk

from ... import __app_name__, __copyright__, __source_url__, __version__
from .. import theme
from ..widgets import Card

NOTICE_WIDTH = 460
DISCLAIMER = (
    "Hasil ekstraksi dibaca otomatis dari PDF dan dapat mengandung kesalahan. "
    "Periksa hasilnya dengan dokumen asli sebelum digunakan.\n\n"
    "Aplikasi ini disediakan apa adanya, tanpa jaminan apa pun. Pembuat tidak "
    "bertanggung jawab atas kerugian yang timbul dari penggunaan aplikasi ini.\n\n"
    "Aplikasi ini bukan bagian dari SIPD. Dokumen asli tetap menjadi acuan resmi."
)
LICENSE_NOTICE = (
    "SmartExtract adalah perangkat lunak bebas. Anda boleh menyebarkan dan mengubahnya "
    "di bawah ketentuan GNU Affero General Public License versi 3."
)


def legal_file(name: str) -> Path:
    """Berkas lisensi: dibundel di dalam exe, atau di akar proyek saat dijalankan dari kode."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "legal" / name
    return Path(__file__).resolve().parents[3] / name


class AboutPage(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        card = Card(self)
        card.grid(row=0, column=0, padx=28, pady=20)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text="", image=theme.icon(theme.ICON_LOGO, 26), width=56, height=56,
            fg_color=theme.ACCENT[1], corner_radius=14,
        ).grid(row=0, column=0, padx=88, pady=(24, 10))
        ctk.CTkLabel(
            card, text=__app_name__, font=theme.font(26, "semibold"), text_color=theme.TEXT, height=36,
        ).grid(row=1, column=0)
        ctk.CTkLabel(
            card, text=f"Versi {__version__}", font=theme.font(14), text_color=theme.MUTED, height=22,
        ).grid(row=2, column=0, pady=(2, 10))
        ctk.CTkLabel(
            card, text=__copyright__, font=theme.font(13), text_color=theme.MUTED, height=20,
        ).grid(row=3, column=0, pady=(0, 14))

        notice = ctk.CTkFrame(card, fg_color=theme.SURFACE_ALT, corner_radius=10)
        notice.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))
        self._add_notice(notice, "Disclaimer", DISCLAIMER)
        self._add_notice(notice, "Lisensi", LICENSE_NOTICE)

        links = ctk.CTkFrame(notice, fg_color="transparent")
        links.pack(anchor="w", padx=16, pady=(8, 12))
        for text, command in (
            ("Teks lisensi", lambda: os.startfile(legal_file("LICENSE.txt"))),
            ("Pihak ketiga", lambda: os.startfile(legal_file("THIRD_PARTY_NOTICES.txt"))),
            ("Kode sumber", lambda: webbrowser.open(__source_url__)),
        ):
            ctk.CTkButton(
                links, text=text, command=command, height=28, width=104, corner_radius=7,
                border_width=1, border_color=theme.BORDER, font=theme.font(12),
                text_color=theme.TEXT, fg_color=theme.SURFACE, hover_color=theme.BORDER,
            ).pack(side="left", padx=(0, 8))

    @staticmethod
    def _add_notice(master, title: str, text: str) -> None:
        ctk.CTkLabel(
            master, text=title, font=theme.font(12, "semibold"), text_color=theme.TEXT, height=18,
        ).pack(anchor="w", padx=16, pady=(10, 2))
        ctk.CTkLabel(
            master, text=text, font=theme.font(12), text_color=theme.MUTED,
            wraplength=NOTICE_WIDTH, justify="left", anchor="w",
        ).pack(anchor="w", padx=16)

    def refresh_theme(self) -> None:
        """Tidak ada yang perlu diatur: warna CustomTkinter mengikuti mode tampilan."""
