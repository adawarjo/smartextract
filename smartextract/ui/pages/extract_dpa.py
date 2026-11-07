# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Menu Extract DPA: PDF DPA Penetapan dan DPPA Parsial/Perubahan."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ...extraction.dpa_parser import (
    PENETAPAN,
    PERUBAHAN,
    HasilDokumen,
    JenisDokumen,
    RekeningRow,
    extract_document,
    format_rupiah,
    tandai_duplikat,
)
from ...extraction.exporter import FORMAT_PENETAPAN, FORMAT_PERUBAHAN
from ...extraction.glyph_reader import GlyphReader
from .extract_base import ExtractPage, MenuConfig


@dataclass(frozen=True)
class DpaMenuConfig(MenuConfig):
    jenis: JenisDokumen
    pagu_heading: str


def _dpa_menu(jenis: JenisDokumen, **options) -> DpaMenuConfig:
    return DpaMenuConfig(
        title=jenis.menu,
        jenis=jenis,
        source_name="PDF",
        folder_pattern="*.pdf",
        file_type=("Dokumen PDF", "*.pdf"),
        search_hint="Cari kode, nama rekening, sumber dana",
        file_extra_heading="Halaman",
        file_extra_width=72,
        **options,
    )


MENU_PENETAPAN = _dpa_menu(
    PENETAPAN,
    subtitle="Ambil rekening belanja dari PDF DPA Rincian Belanja SKPD, lalu cocokkan dengan total dokumen.",
    sample_folder="dpa",
    output_name="rekening_belanja_dpa_penetapan",
    output_format=FORMAT_PENETAPAN,
    pagu_heading="Pagu",
)
MENU_PERUBAHAN = _dpa_menu(
    PERUBAHAN,
    subtitle="Ambil nilai Setelah rekening belanja dari PDF DPPA Rincian Belanja SKPD, lalu cocokkan dengan total dokumen.",
    sample_folder="dpa-per",
    output_name="rekening_belanja_dpa_parsial_perubahan",
    output_format=FORMAT_PERUBAHAN,
    pagu_heading="Pagu Setelah",
)


class ExtractDpaPage(ExtractPage):
    _reader: GlyphReader | None = None

    def _result_table_spec(self) -> dict:
        return {
            "columns": {
                "uraian": {"title": "Uraian"},
                "sumber": {"title": "Sumber Dana", "width": 180},
                "pagu": {"title": self._config.pagu_heading, "width": 130, "anchor": "e"},
            },
            "tree_heading": "Kode",
            "tree_width": 200,
            "fill": "uraian",
        }

    def _prepare(self) -> None:
        if self._reader is None:
            self._events.put(("status", "Menyiapkan mesin baca..."))
            self._reader = GlyphReader()

    def _extract(self, path: Path, on_page) -> HasilDokumen:
        return extract_document(path, self._reader, on_page, self._config.jenis)

    def _check_batch(self) -> None:
        tandai_duplikat(self._results)

    def _file_extra_value(self, result: HasilDokumen) -> str:
        return result.halaman or "-"

    def _search_text(self, row: RekeningRow) -> str:
        return " ".join((
            row.kode_kegiatan, row.nama_kegiatan, row.kode_sub_kegiatan, row.nama_sub_kegiatan,
            row.kode_rekening, row.nama_rekening, row.sumber_dana,
        )).lower()

    def _fill_results(self, rows: list[RekeningRow]) -> None:
        tree = self._result_table.tree
        groups: dict[str, dict[str, list[RekeningRow]]] = {}
        for row in rows:
            groups.setdefault(row.kode_kegiatan, {}).setdefault(row.kode_sub_kegiatan, []).append(row)

        for kode_kegiatan, subs in groups.items():
            first = next(iter(subs.values()))[0]
            total = sum((r.pagu for items in subs.values() for r in items), Decimal(0))
            parent = tree.insert(
                "", "end", text=kode_kegiatan, open=True, tags=("kegiatan",),
                values=(first.nama_kegiatan, f"{len(subs)} sub kegiatan", format_rupiah(total)),
            )
            for kode_sub, items in subs.items():
                total = sum((r.pagu for r in items), Decimal(0))
                node = tree.insert(
                    parent, "end", text=kode_sub, open=True, tags=("sub",),
                    values=(items[0].nama_sub_kegiatan, f"{len(items)} rekening", format_rupiah(total)),
                )
                for row in items:
                    tree.insert(
                        node, "end", text=row.kode_rekening,
                        tags=("masalah",) if row.bermasalah else (),
                        values=(row.nama_rekening, row.sumber_dana, format_rupiah(row.pagu)),
                    )
