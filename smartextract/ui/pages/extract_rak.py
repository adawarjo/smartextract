# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Menu Extract RAK: Excel RAK Belanja tahap Penetapan, Parsial, dan Perubahan."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ...extraction.dpa_parser import HasilDokumen, format_rupiah, tandai_duplikat
from ...extraction.exporter import FORMAT_RAK
from ...extraction.rak_reader import BULAN, KasRow, extract_rak, periksa_tahap
from .extract_base import ExtractPage, MenuConfig

MENU_RAK = MenuConfig(
    title="Extract RAK Penetapan/Parsial/Perubahan",
    subtitle="Ambil anggaran kas per bulan dari Excel RAK Belanja SIPD, lalu cocokkan dengan total dokumen.",
    sample_folder="rak",
    output_name="anggaran_kas",
    output_format=FORMAT_RAK,
    source_name="Excel RAK",
    folder_pattern="RAK_*.xlsx",
    file_type=("Excel RAK", "*.xlsx"),
    search_hint="Cari kode atau nama rekening",
    file_extra_heading="Tahap",
    file_extra_width=150,
)


def _angka(value: Decimal) -> str:
    return format_rupiah(value).replace("Rp", "")


class ExtractRakPage(ExtractPage):
    def _result_table_spec(self) -> dict:
        columns = {"uraian": {"title": "Uraian"}, "pagu": {"title": "Pagu", "width": 124, "anchor": "e"}}
        for bulan in BULAN:
            columns[bulan] = {"title": bulan.capitalize(), "width": 96, "anchor": "e"}
        return {
            "columns": columns,
            "tree_heading": "Kode",
            "tree_width": 200,
            "fill": "uraian",
            "fill_min": 330,
            "horizontal": True,
        }

    def _extract(self, path: Path, on_page) -> HasilDokumen:
        return extract_rak(path)

    def _check_batch(self) -> None:
        tandai_duplikat(self._results, lambda row: (row.kode_sub_kegiatan, row.kode_rekening))
        periksa_tahap(self._results)

    def _tahap_tunggal(self) -> str:
        tahap = {result.tahap for result in self._results if result.tahap}
        return tahap.pop() if len(tahap) == 1 else ""

    def _summary_note(self) -> str:
        tahap = self._tahap_tunggal()
        return f" Tahap dokumen: {tahap}." if tahap else ""

    def _output_name(self) -> str:
        tahap = self._tahap_tunggal().replace(" ", "_")
        return f"{self._config.output_name}_{tahap}" if tahap else self._config.output_name

    def _file_extra_value(self, result: HasilDokumen) -> str:
        return result.tahap or "-"

    def _search_text(self, row: KasRow) -> str:
        return " ".join((
            row.kode_sub_kegiatan, row.nama_sub_kegiatan, row.kode_rekening, row.nama_rekening,
        )).lower()

    def _fill_results(self, rows: list[KasRow]) -> None:
        tree = self._result_table.tree
        groups: dict[str, list[KasRow]] = {}
        for row in rows:
            groups.setdefault(row.kode_sub_kegiatan, []).append(row)

        for kode_sub, items in groups.items():
            bulanan = [sum((getattr(r, bulan) for r in items), Decimal(0)) for bulan in BULAN]
            total = sum((r.pagu for r in items), Decimal(0))
            node = tree.insert(
                "", "end", text=kode_sub, open=True, tags=("sub",),
                values=(items[0].nama_sub_kegiatan, format_rupiah(total), *map(_angka, bulanan)),
            )
            for row in items:
                tree.insert(
                    node, "end", text=row.kode_rekening,
                    tags=("masalah",) if row.bermasalah else (),
                    values=(
                        row.nama_rekening, format_rupiah(row.pagu),
                        *(_angka(getattr(row, bulan)) for bulan in BULAN),
                    ),
                )
