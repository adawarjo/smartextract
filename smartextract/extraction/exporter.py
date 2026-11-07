# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Menulis hasil ekstraksi ke CSV (format template) dan Excel."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

COLUMNS = (
    "kode_kegiatan",
    "nama_kegiatan",
    "kode_sub_kegiatan",
    "nama_sub_kegiatan",
    "kode_rekening",
    "nama_rekening",
    "pagu",
    "sumber_dana",
    "keterangan",
)
_COLUMN_WIDTHS = (14, 38, 19, 58, 22, 58, 16, 26, 16)
_BULAN = ("jan", "feb", "mar", "apr", "mei", "jun", "jul", "agu", "sep", "okt", "nov", "des")


@dataclass(frozen=True)
class OutputFormat:
    """Kolom dan gaya berkas hasil, mengikuti template tiap menu.

    Semua CSV memakai UTF-8 BOM dan pemisah titik koma.
    """

    columns: tuple[str, ...]
    widths: tuple[int, ...]
    sheet_title: str
    line_end: str
    numeric: tuple[str, ...] = ("pagu",)
    quoted: tuple[str, ...] = ()


FORMAT_PENETAPAN = OutputFormat(COLUMNS, _COLUMN_WIDTHS, "Rekening Belanja", "\r\n")
FORMAT_PERUBAHAN = OutputFormat(
    COLUMNS, _COLUMN_WIDTHS, "Rekening Belanja", "\n",
    quoted=("nama_kegiatan", "nama_sub_kegiatan", "nama_rekening", "sumber_dana"),
)
FORMAT_RAK = OutputFormat(
    ("kode_sub_kegiatan", "kode_rekening", "nama_rekening", "pagu", *_BULAN),
    (19, 22, 58, 16, *([14] * 12)),
    "Anggaran Kas",
    "\n",
    numeric=("pagu", *_BULAN),
    quoted=("nama_rekening",),
)


def _number_csv(value: Decimal) -> str:
    """Bilangan bulat tanpa pemisah ribuan seperti template; desimal memakai koma."""
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f").replace(".", ",")


def _number_excel(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def _csv_cell(value: str, always_quote: bool) -> str:
    if always_quote or any(char in value for char in ';"\r\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def to_csv(rows: Sequence, path: Path, fmt: OutputFormat = FORMAT_PENETAPAN) -> None:
    lines = [";".join(fmt.columns)]
    for row in rows:
        lines.append(";".join(
            _number_csv(getattr(row, column)) if column in fmt.numeric
            else _csv_cell(getattr(row, column), column in fmt.quoted)
            for column in fmt.columns
        ))
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        stream.write(fmt.line_end.join(lines) + fmt.line_end)


def to_xlsx(rows: Sequence, path: Path, fmt: OutputFormat = FORMAT_PENETAPAN) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = fmt.sheet_title
    sheet.append(fmt.columns)

    for row in rows:
        sheet.append([
            _number_excel(getattr(row, column)) if column in fmt.numeric else getattr(row, column)
            for column in fmt.columns
        ])

    thin = Side(style="thin", color="D9DEE7")
    header_fill = PatternFill("solid", fgColor="1E3A8A")
    for cell in sheet[1]:
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 22

    for index, width in enumerate(fmt.widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    number_columns = [fmt.columns.index(column) for column in fmt.numeric]
    for data_row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
        for cell in data_row:
            cell.border = Border(bottom=thin)
        for index in number_columns:
            data_row[index].number_format = "#,##0"

    sheet.freeze_panes = "A2"
    if rows:
        sheet.auto_filter.ref = sheet.dimensions
    workbook.save(path)
