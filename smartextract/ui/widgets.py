# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Komponen UI yang dipakai ulang antarhalaman."""

from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

from . import theme

MIN_FILL_WIDTH = 100


class Card(ctk.CTkFrame):
    """Panel putih berbingkai tipis."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=theme.SURFACE,
            border_color=theme.BORDER,
            border_width=1,
            corner_radius=12,
            **kwargs,
        )


class StatCard(Card):
    """Satu angka ringkasan dengan judul kecil."""

    def __init__(self, master, title: str, value: str = "-") -> None:
        super().__init__(master, height=78)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=theme.font(12), text_color=theme.MUTED, height=18).grid(
            row=0, column=0, sticky="w", padx=16, pady=(13, 0)
        )
        self._value = ctk.CTkLabel(self, text=value, font=theme.font(20, "semibold"), text_color=theme.TEXT, height=30)
        self._value.grid(row=1, column=0, sticky="w", padx=16, pady=(2, 10))

    def set(self, value: str, color=None) -> None:
        self._value.configure(text=value, text_color=color or theme.TEXT)


class DataTree(ctk.CTkFrame):
    """Treeview ttk bertema aplikasi, lengkap dengan scrollbar.

    Satu kolom (`fill`) mengisi sisa lebar. Pembagian ini dihitung sendiri karena
    stretch bawaan ttk gagal menyusutkan kolom saat lebar awal melebihi jendela,
    sehingga kolom paling kanan bisa terdorong keluar dari tampilan. Tabel yang
    lebih lebar dari layar memakai `horizontal` untuk scrollbar mendatar.
    """

    def __init__(
        self,
        master,
        columns: dict[str, dict],
        tree_heading: str,
        tree_width: int,
        fill: str,
        fill_min: int = MIN_FILL_WIDTH,
        horizontal: bool = False,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        scale = ctk.ScalingTracker.get_window_dpi_scaling(self.winfo_toplevel())
        self._fill = fill
        self._fill_min = int(fill_min * scale)

        self.tree = ttk.Treeview(self, columns=list(columns), style="App.Treeview", selectmode="browse")
        self.tree.heading("#0", text=tree_heading, anchor="w")
        self.tree.column("#0", width=int(tree_width * scale), minwidth=120, stretch=False)
        for name, options in columns.items():
            self.tree.heading(name, text=options["title"], anchor=options.get("anchor", "w"))
            self.tree.column(
                name,
                width=int(options.get("width", 120) * scale),
                minwidth=60,
                anchor=options.get("anchor", "w"),
                stretch=False,
            )
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Configure>", self._fit_columns)

        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview, width=14)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        self.tree.configure(yscrollcommand=scrollbar.set)
        if horizontal:
            bottom = ctk.CTkScrollbar(self, command=self.tree.xview, height=14, orientation="horizontal")
            bottom.grid(row=1, column=0, sticky="ew", pady=(2, 0))
            self.tree.configure(xscrollcommand=bottom.set)
        self.refresh_tags()

    def _fit_columns(self, event) -> None:
        others = ["#0", *self.tree["columns"]]
        others.remove(self._fill)
        used = sum(self.tree.column(name, "width") for name in others)
        self.tree.column(self._fill, width=max(event.width - used, self._fill_min))

    def refresh_tags(self) -> None:
        tree = self.tree
        tree.tag_configure("kegiatan", font=("Segoe UI Semibold", 10), background=theme.pick(theme.ACCENT_SOFT))
        tree.tag_configure("sub", font=("Segoe UI Semibold", 10), background=theme.pick(theme.SURFACE_ALT))
        tree.tag_configure("masalah", foreground=theme.pick(theme.WARNING))
        tree.tag_configure("ok", foreground=theme.pick(theme.SUCCESS))
        tree.tag_configure("peringatan", foreground=theme.pick(theme.WARNING))
        tree.tag_configure("gagal", foreground=theme.pick(theme.DANGER))

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())
