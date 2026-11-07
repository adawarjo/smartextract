# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Dasar halaman ekstraksi: pilih sumber, proses di latar, tampilkan hasil, lalu simpan."""

from __future__ import annotations

import fnmatch
import os
import queue
import sys
import threading
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from ...extraction.dpa_parser import HasilDokumen, format_rupiah
from ...extraction.exporter import OutputFormat, to_csv, to_xlsx
from .. import theme
from ..widgets import Card, DataTree, StatCard

TAB_RESULTS = "Hasil Ekstraksi"
TAB_FILES = "Status File"
FINDINGS_BASE_HEIGHT = 14
FINDINGS_LINE_HEIGHT = 17
FINDINGS_MAX_HEIGHT = 124


@dataclass(frozen=True)
class MenuConfig:
    """Hal yang membedakan menu-menu ekstraksi."""

    title: str
    subtitle: str
    sample_folder: str
    output_name: str
    output_format: OutputFormat
    source_name: str                # sebutan sumber di layar, mis. "PDF"
    folder_pattern: str             # file yang diambil saat sumber berupa folder
    file_type: tuple[str, str]      # label dan pola pada dialog pilih file
    search_hint: str
    file_extra_heading: str         # kolom tambahan di tab Status File
    file_extra_width: int


def sample_root() -> Path:
    """Folder contoh: di samping exe, atau di akar proyek saat dijalankan dari kode."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "sample"
    return Path(__file__).resolve().parents[3] / "sample"


def list_files(folder: Path, pattern: str) -> list[Path]:
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and fnmatch.fnmatch(p.name.lower(), pattern.lower())),
        key=lambda p: p.name,
    )


class ExtractPage(ctk.CTkFrame):
    """Turunan mengisi bagian yang berbeda: cara membaca file dan bentuk tabel hasil."""

    def __init__(self, master, config: MenuConfig) -> None:
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self._config = config
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._paths: list[Path] = []
        self._results: list[HasilDokumen] = []
        self._events: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._running = False
        self._saved_path: Path | None = None
        self._search_job: str | None = None

        self._build_header()
        self._build_source_card()
        self._build_stats()
        self._build_results()
        self._build_footer()

        sample = sample_root() / config.sample_folder
        if sample.is_dir():
            self.load_folder(sample)
        else:
            self._update_ready_state()

    # ---- bagian yang diisi turunan ---------------------------------------

    def _result_table_spec(self) -> dict:
        """Argumen DataTree untuk tabel hasil."""
        raise NotImplementedError

    def _fill_results(self, rows: list) -> None:
        raise NotImplementedError

    def _search_text(self, row) -> str:
        raise NotImplementedError

    def _extract(self, path: Path, on_page: Callable[[int, int], None]) -> HasilDokumen:
        raise NotImplementedError

    def _file_extra_value(self, result: HasilDokumen) -> str:
        raise NotImplementedError

    def _prepare(self) -> None:
        """Persiapan sebelum file pertama; berjalan di thread latar."""

    def _check_batch(self) -> None:
        """Pemeriksaan antarfile setelah semua file selesai."""

    def _summary_note(self) -> str:
        """Tambahan pada pesan selesai."""
        return ""

    def _output_name(self) -> str:
        return self._config.output_name

    # ---- susunan tampilan ------------------------------------------------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 14))
        ctk.CTkLabel(
            header, text=self._config.title, font=theme.font(24, "semibold"),
            text_color=theme.TEXT, height=32,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=self._config.subtitle,
            font=theme.font(13), text_color=theme.MUTED, height=20,
        ).pack(anchor="w")

    def _build_source_card(self) -> None:
        card = Card(self)
        card.grid(row=1, column=0, sticky="ew", padx=28)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text=f"Sumber {self._config.source_name}", font=theme.font(12, "semibold"),
            text_color=theme.MUTED, height=18,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(14, 6))

        self._source = ctk.CTkEntry(
            card, height=38, corner_radius=8, border_width=1, border_color=theme.BORDER,
            fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, font=theme.font(13),
            placeholder_text=f"Pilih folder atau file {self._config.source_name}", state="disabled",
        )
        self._source.grid(row=1, column=0, sticky="ew", padx=(18, 8))

        self._folder_button = self._secondary_button(card, "Folder", theme.ICON_FOLDER, self._choose_folder)
        self._folder_button.grid(row=1, column=1, padx=(0, 8))
        self._files_button = self._secondary_button(card, "File", theme.ICON_FILES, self._choose_files)
        self._files_button.grid(row=1, column=2, padx=(0, 8))

        self._start_button = ctk.CTkButton(
            card, text="Mulai Ekstraksi", image=theme.icon(theme.ICON_PLAY, 14), compound="left",
            height=38, width=170, corner_radius=8, font=theme.font(13, "semibold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._on_start_clicked,
        )
        self._start_button.grid(row=1, column=3, padx=(0, 18))

        progress_row = ctk.CTkFrame(card, fg_color="transparent")
        progress_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=18, pady=(10, 14))
        progress_row.grid_columnconfigure(0, weight=1)
        self._status = ctk.CTkLabel(progress_row, text="", font=theme.font(12), text_color=theme.MUTED, height=18, anchor="w")
        self._status.grid(row=0, column=0, sticky="ew")
        self._progress = ctk.CTkProgressBar(
            progress_row, height=6, corner_radius=3, fg_color=theme.SURFACE_ALT, progress_color=theme.ACCENT,
        )
        self._progress.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self._progress.set(0)

    def _secondary_button(self, master, text, glyph, command, width=96) -> ctk.CTkButton:
        return ctk.CTkButton(
            master, text=text, image=theme.icon(glyph, 15, theme.TEXT), compound="left",
            height=38, width=width, corner_radius=8, border_width=1, border_color=theme.BORDER,
            font=theme.font(13), text_color=theme.TEXT, text_color_disabled=theme.MUTED,
            fg_color=theme.SURFACE, hover_color=theme.SURFACE_ALT, command=command,
        )

    def _build_stats(self) -> None:
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=2, column=0, sticky="ew", padx=28, pady=12)
        for column, weight in enumerate((2, 2, 2, 3, 3)):
            stats.grid_columnconfigure(column, weight=weight, uniform="stat")

        self._stat_files = StatCard(stats, "File diproses")
        self._stat_subs = StatCard(stats, "Sub kegiatan")
        self._stat_rows = StatCard(stats, "Rekening")
        self._stat_total = StatCard(stats, "Total pagu")
        self._stat_check = StatCard(stats, "Validasi")
        cards = (self._stat_files, self._stat_subs, self._stat_rows, self._stat_total, self._stat_check)
        for column, card in enumerate(cards):
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0 if column == 4 else 6))

    def _build_results(self) -> None:
        card = Card(self)
        card.grid(row=3, column=0, sticky="nsew", padx=28)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(card, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 10))
        toolbar.grid_columnconfigure(1, weight=1)

        self._view = ctk.StringVar(value=TAB_RESULTS)
        self._tabs = ctk.CTkSegmentedButton(
            toolbar, values=[TAB_RESULTS, TAB_FILES], variable=self._view, command=self._show_tab,
            font=theme.font(13), height=34, corner_radius=8, fg_color=theme.SURFACE_ALT,
            unselected_color=theme.SURFACE_ALT, unselected_hover_color=theme.BORDER,
            selected_color=theme.ACCENT_SOFT, selected_hover_color=theme.ACCENT_SOFT,
            text_color=theme.TEXT,
        )
        self._tabs.grid(row=0, column=0, sticky="w")

        self._search = ctk.CTkEntry(
            toolbar, width=280, height=34, corner_radius=8, border_width=1, border_color=theme.BORDER,
            fg_color=theme.SURFACE_ALT, text_color=theme.TEXT, font=theme.font(13),
            placeholder_text=self._config.search_hint,
            placeholder_text_color=theme.MUTED,
        )
        self._search.grid(row=0, column=2, sticky="e")
        self._search.bind("<KeyRelease>", self._on_search_changed)

        self._holder = ctk.CTkFrame(card, fg_color="transparent")
        self._holder.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 12))
        self._holder.grid_columnconfigure(0, weight=1)
        self._holder.grid_rowconfigure(0, weight=1)

        self._result_table = DataTree(self._holder, **self._result_table_spec())
        self._result_table.grid(row=0, column=0, sticky="nsew")

        self._file_view = ctk.CTkFrame(self._holder, fg_color="transparent")
        self._file_view.grid_columnconfigure(0, weight=1)
        self._file_view.grid_rowconfigure(0, weight=1)
        self._file_table = DataTree(
            self._file_view,
            columns={
                "tambahan": {
                    "title": self._config.file_extra_heading,
                    "width": self._config.file_extra_width,
                    "anchor": "center",
                },
                "sub": {"title": "Sub Kegiatan", "width": 96, "anchor": "center"},
                "rekening": {"title": "Rekening", "width": 80, "anchor": "center"},
                "total": {"title": "Total Pagu", "width": 130, "anchor": "e"},
                "waktu": {"title": "Waktu", "width": 70, "anchor": "e"},
                "status": {"title": "Status", "width": 140},
            },
            tree_heading="File",
            tree_width=400,
            fill="#0",
        )
        self._file_table.grid(row=0, column=0, sticky="nsew")
        self._findings = ctk.CTkTextbox(
            self._file_view, height=120, corner_radius=8, border_width=0, wrap="word",
            font=theme.font(12), fg_color=theme.SURFACE_ALT, text_color=theme.TEXT,
            state="disabled",
        )
        self._color_findings()

        self._empty = ctk.CTkLabel(
            self._holder,
            text=f"Belum ada hasil.\nPilih sumber {self._config.source_name}, lalu klik Mulai Ekstraksi.",
            font=theme.font(14), text_color=theme.MUTED, fg_color=theme.SURFACE, justify="center",
        )
        self._empty.place(relx=0.5, rely=0.55, anchor="center")

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=28, pady=(12, 18))
        footer.grid_columnconfigure(0, weight=1)

        self._save_status = ctk.CTkLabel(footer, text="", font=theme.font(12), text_color=theme.MUTED, anchor="w", height=38)
        self._save_status.grid(row=0, column=0, sticky="ew")
        self._open_button = self._secondary_button(footer, "Buka File", theme.ICON_OPEN, self._open_saved, width=110)

        self._csv_button = self._secondary_button(footer, "Simpan CSV", theme.ICON_SAVE, self._save_csv, width=130)
        self._csv_button.grid(row=0, column=2, padx=(8, 8))
        self._xlsx_button = ctk.CTkButton(
            footer, text="Simpan Excel", image=theme.icon(theme.ICON_EXPORT, 15), compound="left",
            height=38, width=140, corner_radius=8, font=theme.font(13, "semibold"),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._save_xlsx,
        )
        self._xlsx_button.grid(row=0, column=3)

    def refresh_theme(self) -> None:
        self._result_table.refresh_tags()
        self._file_table.refresh_tags()
        self._color_findings()

    def _color_findings(self) -> None:
        self._findings.tag_config("error", foreground=theme.pick(theme.DANGER))
        self._findings.tag_config("warning", foreground=theme.pick(theme.WARNING))
        self._findings.tag_config("info", foreground=theme.pick(theme.MUTED))

    # ---- pemilihan sumber ------------------------------------------------

    def load_folder(self, folder: Path) -> None:
        self._set_source(list_files(folder, self._config.folder_pattern), str(folder))

    def load_files(self, paths: list[Path]) -> None:
        label = str(paths[0]) if len(paths) == 1 else f"{len(paths)} file dipilih dari {paths[0].parent}"
        self._set_source(sorted(paths, key=lambda p: p.name), label)

    def _set_source(self, paths: list[Path], label: str) -> None:
        self._paths = paths
        self._source.configure(state="normal")
        self._source.delete(0, "end")
        self._source.insert(0, label)
        self._source.configure(state="disabled")
        self._update_ready_state()

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title=f"Pilih folder berisi {self._config.source_name}")
        if folder:
            self.load_folder(Path(folder))

    def _choose_files(self) -> None:
        files = filedialog.askopenfilenames(
            title=f"Pilih {self._config.source_name}", filetypes=[self._config.file_type],
        )
        if files:
            self.load_files([Path(f) for f in files])

    def _update_ready_state(self) -> None:
        count = len(self._paths)
        source = self._config.source_name
        if count:
            message = f"{count} file {source} siap diproses."
        elif self._source.get():
            message = f"Tidak ada file {source} di sumber ini."
        else:
            message = f"Pilih folder atau file {source} untuk memulai."
        self._status.configure(text=message, text_color=theme.MUTED)
        self._progress.set(0)
        self._start_button.configure(state="normal" if count else "disabled")
        self._update_export_state()

    def _update_export_state(self) -> None:
        state = "normal" if self.rows and not self._running else "disabled"
        self._csv_button.configure(state=state)
        self._xlsx_button.configure(state=state)

    # ---- proses ekstraksi ------------------------------------------------

    def _on_start_clicked(self) -> None:
        if self._running:
            self._cancel.set()
            self._start_button.configure(state="disabled", text="Membatalkan...")
        else:
            self.start()

    def start(self) -> None:
        if self._running or not self._paths:
            return
        self._running = True
        self._cancel.clear()
        self._results = []
        self._set_saved(None)
        self._render_all()
        self._folder_button.configure(state="disabled")
        self._files_button.configure(state="disabled")
        self._start_button.configure(
            text="Batalkan", image=theme.icon(theme.ICON_STOP, 13),
            fg_color=theme.DANGER_FILL, hover_color=theme.DANGER_HOVER,
        )
        self._update_export_state()
        threading.Thread(target=self._work, args=(list(self._paths),), daemon=True).start()
        self.after(50, self._poll_events)

    def _work(self, paths: list[Path]) -> None:
        """Berjalan di thread terpisah; UI hanya diperbarui lewat antrean event."""
        try:
            self._prepare()
        except Exception as error:
            self._events.put(("fatal", str(error)))
            return

        for index, path in enumerate(paths):
            if self._cancel.is_set():
                break
            self._events.put(("status", f"Memproses {index + 1} dari {len(paths)}: {path.name}"))

            def on_page(page: int, pages: int, index: int = index) -> None:
                self._events.put(("progress", (index + page / pages) / len(paths)))

            self._events.put(("result", self._extract(path, on_page)))
            self._events.put(("progress", (index + 1) / len(paths)))
        self._events.put(("done", self._cancel.is_set()))

    def _poll_events(self) -> None:
        finished = False
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "status":
                    self._status.configure(text=payload, text_color=theme.MUTED)
                elif kind == "progress":
                    self._progress.set(payload)
                elif kind == "result":
                    self._results.append(payload)
                    self._render_stats()
                elif kind == "fatal":
                    messagebox.showerror("Tidak bisa memulai", payload)
                    finished = True
                elif kind == "done":
                    self._finish(cancelled=payload)
                    finished = True
        except queue.Empty:
            pass
        if finished:
            self._running = False
            self._restore_controls()
        else:
            self.after(50, self._poll_events)

    def _finish(self, cancelled: bool) -> None:
        self._check_batch()
        self._render_all()
        done = len(self._results)
        failed = sum(1 for result in self._results if result.gagal)
        findings = sum(len(result.masalah) for result in self._results)
        notes = sum(len(result.temuan) - len(result.masalah) for result in self._results)
        seconds = sum(result.detik for result in self._results)

        message = f"Selesai: {done} file dalam {seconds:.1f} detik.{self._summary_note()}"
        if notes:
            message += f" Ada {notes} catatan di tab Status File."
        color = theme.SUCCESS
        if cancelled:
            message = f"Dibatalkan. {done} dari {len(self._paths)} file sudah diproses."
            color = theme.WARNING
        elif failed:
            message = f"Selesai dengan {failed} file gagal; file tersebut tidak ikut tersimpan. Lihat tab Status File."
            color = theme.DANGER
        elif findings:
            message = f"Selesai dengan {findings} temuan. Mohon periksa tab Status File sebelum memakai data."
            color = theme.WARNING
        self._status.configure(text=message, text_color=color)
        self._progress.set(1 if not cancelled else self._progress.get())
        if findings or failed:
            self._view.set(TAB_FILES)
            self._show_tab(TAB_FILES)

    def _restore_controls(self) -> None:
        self._folder_button.configure(state="normal")
        self._files_button.configure(state="normal")
        self._start_button.configure(
            state="normal", text="Mulai Ekstraksi", image=theme.icon(theme.ICON_PLAY, 14),
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
        )
        self._update_export_state()

    # ---- penyajian hasil -------------------------------------------------

    @property
    def rows(self) -> list:
        return [row for result in self._results for row in result.rows]

    def _render_all(self) -> None:
        self._render_stats()
        self._render_results()
        self._render_files()

    def _render_stats(self) -> None:
        results = self._results
        if not results:
            for card in (self._stat_files, self._stat_subs, self._stat_rows, self._stat_total, self._stat_check):
                card.set("-")
            return
        rows = self.rows
        self._stat_files.set(f"{len(results)}")
        self._stat_subs.set(f"{len({row.kode_sub_kegiatan for row in rows})}")
        self._stat_rows.set(f"{len(rows)}")
        self._stat_total.set(format_rupiah(sum((row.pagu for row in rows), Decimal(0))))

        failed = sum(1 for result in results if result.gagal)
        findings = sum(len(result.masalah) for result in results)
        if failed:
            self._stat_check.set(f"{failed} file gagal", theme.DANGER)
        elif findings:
            self._stat_check.set(f"{findings} temuan", theme.WARNING)
        else:
            self._stat_check.set("Total cocok", theme.SUCCESS)

    def _render_results(self) -> None:
        self._result_table.clear()
        query = self._search.get().strip().lower()
        self._fill_results([row for row in self.rows if not query or query in self._search_text(row)])

        if self.rows:
            self._empty.place_forget()
        elif self._view.get() == TAB_RESULTS and not self._running:
            self._empty.place(relx=0.5, rely=0.55, anchor="center")

    def _render_files(self) -> None:
        table = self._file_table
        table.clear()
        for result in self._results:
            if result.gagal:
                status, tag = "Gagal", "gagal"
            elif result.masalah:
                status, tag = f"{len(result.masalah)} temuan", "peringatan"
            else:
                status, tag = "Cocok", "ok"
            table.tree.insert(
                "", "end", text=result.path.name, tags=(tag,),
                values=(
                    self._file_extra_value(result), result.jumlah_sub_kegiatan, len(result.rows),
                    format_rupiah(result.total), f"{result.detik:.1f} dtk", status,
                ),
            )
        self._render_findings()

    def _render_findings(self) -> None:
        box = self._findings
        with_findings = [result for result in self._results if result.temuan]
        box.configure(state="normal")
        box.delete("1.0", "end")
        for result in with_findings:
            box.insert("end", f"{result.path.name}\n")
            for item in result.temuan:
                box.insert("end", f"  • {item.pesan}\n", item.level)
        box.configure(state="disabled")
        if with_findings:
            lines = sum(1 + len(result.temuan) for result in with_findings)
            box.configure(height=min(FINDINGS_BASE_HEIGHT + lines * FINDINGS_LINE_HEIGHT, FINDINGS_MAX_HEIGHT))
            box.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        else:
            box.grid_remove()

    def _show_tab(self, name: str) -> None:
        show_results = name == TAB_RESULTS
        (self._result_table if show_results else self._file_view).grid(row=0, column=0, sticky="nsew")
        (self._file_view if show_results else self._result_table).grid_remove()
        if show_results:
            self._search.grid(row=0, column=2, sticky="e")
        else:
            self._search.grid_remove()
        if self._results:
            self._empty.place_forget()

    def _on_search_changed(self, *_) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(180, self._render_results)

    # ---- penyimpanan -----------------------------------------------------

    def _ask_save_path(self, extension: str, label: str) -> Path | None:
        source = self._paths[0].parent if self._paths else Path.cwd()
        target = filedialog.asksaveasfilename(
            title=f"Simpan {label}", defaultextension=extension,
            initialdir=str(source), initialfile=self._output_name() + extension,
            filetypes=[(label, f"*{extension}")],
        )
        return Path(target) if target else None

    def _save_csv(self) -> None:
        if path := self._ask_save_path(".csv", "CSV"):
            self.save(path)

    def _save_xlsx(self) -> None:
        if path := self._ask_save_path(".xlsx", "Excel"):
            self.save(path)

    def save(self, path: Path) -> None:
        try:
            if path.suffix.lower() == ".xlsx":
                to_xlsx(self.rows, path, self._config.output_format)
            else:
                to_csv(self.rows, path, self._config.output_format)
        except PermissionError:
            messagebox.showerror(
                "Gagal menyimpan",
                f"{path.name} sedang dibuka di aplikasi lain. Tutup dulu file tersebut, lalu simpan lagi.",
            )
            return
        except OSError as error:
            messagebox.showerror("Gagal menyimpan", str(error))
            return
        self._set_saved(path)

    def _set_saved(self, path: Path | None) -> None:
        self._saved_path = path
        if path:
            self._save_status.configure(text=f"Tersimpan: {path.name}", text_color=theme.SUCCESS)
            self._open_button.grid(row=0, column=1, padx=(8, 0))
        else:
            self._save_status.configure(text="")
            self._open_button.grid_remove()

    def _open_saved(self) -> None:
        if self._saved_path and self._saved_path.exists():
            os.startfile(self._saved_path)
