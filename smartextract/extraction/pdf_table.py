# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Menyusun isi halaman PDF menjadi baris tabel memakai garis vector dokumen."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import pymupdf

from .glyph_reader import GlyphReader, OutlineGlyph, make_glyph

RULE_MIN_LENGTH = 8.0       # pt; lebih pendek dari ini bukan garis tabel
RULE_MAX_THICKNESS = 1.5    # pt
RULE_MERGE_TOLERANCE = 1.2  # pt
MAX_GLYPH_SIZE = 14.0       # pt
DEFAULT_EM = 7.5            # pt; ukuran isi tabel DPA bila tak bisa diukur
LINE_SPLIT_EM = 0.6         # jarak titik tengah vertikal antar-baris teks


class UnsupportedPdfError(RuntimeError):
    """PDF tidak bisa dibaca oleh mesin ini."""


@dataclass(slots=True)
class TextLine:
    text: str
    confidence: float


@dataclass(slots=True)
class TableRow:
    page: int
    cells: list[list[TextLine]] = field(default_factory=list)

    @property
    def lines(self) -> list[TextLine]:
        return [line for cell in self.cells for line in cell]


def _is_dark(drawing: dict) -> bool:
    fill = drawing.get("fill")
    return fill is not None and max(fill) <= 0.3


def _has_ink(drawing: dict) -> bool:
    """Warna yang cukup kontras untuk huruf: nilai pengurangan di DPPA dicetak merah,
    sedangkan latar sel berwarna putih atau abu-abu muda.
    """
    fill = drawing.get("fill")
    return fill is not None and min(fill) <= 0.5


def _collect_rules(drawings: list[dict]) -> tuple[list, list]:
    horizontal, vertical = [], []
    for drawing in filter(_is_dark, drawings):
        for item in drawing["items"]:
            if item[0] != "re":
                continue
            rect = item[1]
            if rect.width >= RULE_MIN_LENGTH and rect.height <= RULE_MAX_THICKNESS:
                horizontal.append(rect)
            elif rect.height >= RULE_MIN_LENGTH and rect.width <= RULE_MAX_THICKNESS:
                vertical.append(rect)
    return horizontal, vertical


def _extract_glyphs(drawings: list[dict]) -> list[OutlineGlyph]:
    """Ambil path huruf; garis tabel dan bidang warna dilewati."""
    glyphs = []
    for drawing in filter(_has_ink, drawings):
        items = drawing["items"]
        if all(item[0] == "re" for item in items):
            # Huruf persegi yang berdempetan ("III", "l-") tergabung dalam satu path,
            # jadi tiap persegi diperiksa sendiri-sendiri.
            glyphs += [
                make_glyph([item], item[1])
                for item in items
                if item[1].width < RULE_MIN_LENGTH and item[1].height < RULE_MIN_LENGTH
            ]
        elif drawing["rect"].width < MAX_GLYPH_SIZE and drawing["rect"].height < MAX_GLYPH_SIZE:
            glyphs.append(make_glyph(items, drawing["rect"]))
    return glyphs


def _is_rule_stub(glyph: OutlineGlyph, em: float) -> bool:
    """Potongan garis pendek: persegi yang tingginya tidak cocok dengan huruf mana pun."""
    return glyph.is_rectangle and 0.3 * em < glyph.y1 - glyph.y0 < 0.62 * em


def _row_edges(horizontal: list, page_height: float) -> list[float]:
    edges: list[float] = []
    for y in sorted((r.y0 + r.y1) / 2 for r in horizontal):
        if not edges or y - edges[-1] > RULE_MERGE_TOLERANCE:
            edges.append(y)
    return [0.0, *edges, page_height]


def _column_index(center: float, dividers: list[float]) -> int:
    return sum(1 for x in dividers if x < center)


def _dividers(vertical: list, middle: float) -> list[float]:
    return sorted((r.x0 + r.x1) / 2 for r in vertical if r.y0 <= middle <= r.y1)


def _split_lines(glyphs: list[OutlineGlyph], em: float) -> list[list[OutlineGlyph]]:
    lines: list[list[OutlineGlyph]] = []
    previous = None
    for glyph in sorted(glyphs, key=lambda g: (g.y0 + g.y1) / 2):
        center = (glyph.y0 + glyph.y1) / 2
        if previous is None or center - previous > LINE_SPLIT_EM * em:
            lines.append([])
        lines[-1].append(glyph)
        previous = center
    return lines


def _read_outline_page(page, drawings, glyphs, number, reader: GlyphReader, em: float) -> list[TableRow]:
    horizontal, vertical = _collect_rules(drawings)
    glyphs = [g for g in glyphs if not _is_rule_stub(g, em)]
    edges = _row_edges(horizontal, page.rect.height)

    rows = []
    for top, bottom in zip(edges, edges[1:]):
        inside = [g for g in glyphs if top <= (g.y0 + g.y1) / 2 < bottom]
        if not inside:
            continue
        dividers = _dividers(vertical, (top + bottom) / 2)
        columns: dict[int, list[OutlineGlyph]] = {}
        for glyph in inside:
            columns.setdefault(_column_index((glyph.x0 + glyph.x1) / 2, dividers), []).append(glyph)

        row = TableRow(page=number)
        for key in sorted(columns):
            cell = []
            for line in _split_lines(columns[key], em):
                cell.append(TextLine(*reader.read_line(line, em)))
            row.cells.append(cell)
        rows.append(row)
    return rows


def _read_text_page(page, drawings, number) -> list[TableRow]:
    """Halaman yang punya text layer asli: teksnya dipakai langsung."""
    horizontal, vertical = _collect_rules(drawings)
    edges = _row_edges(horizontal, page.rect.height)
    words = page.get_text("words")

    rows = []
    for top, bottom in zip(edges, edges[1:]):
        inside = [w for w in words if top <= (w[1] + w[3]) / 2 < bottom]
        if not inside:
            continue
        dividers = _dividers(vertical, (top + bottom) / 2)
        columns: dict[int, list] = {}
        for word in inside:
            columns.setdefault(_column_index((word[0] + word[2]) / 2, dividers), []).append(word)

        row = TableRow(page=number)
        for key in sorted(columns):
            lines: dict[tuple, list] = {}
            for word in columns[key]:
                lines.setdefault((word[5], word[6]), []).append(word)
            row.cells.append([
                TextLine(" ".join(w[4] for w in sorted(group, key=lambda w: w[0])), 1.0)
                for group in sorted(lines.values(), key=lambda g: g[0][1])
            ])
        rows.append(row)
    return rows


def read_table_rows(
    path: Path,
    reader: GlyphReader,
    on_page: Callable[[int, int], None] | None = None,
) -> Iterator[TableRow]:
    """Hasilkan seluruh baris tabel PDF, urut halaman lalu dari atas ke bawah."""
    try:
        document = pymupdf.open(path)
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as error:
        raise UnsupportedPdfError("File rusak atau bukan PDF.") from error

    with document:
        if document.needs_pass:
            raise UnsupportedPdfError("PDF dilindungi kata sandi.")
        if document.page_count == 0:
            raise UnsupportedPdfError("PDF tidak memiliki halaman.")

        pages = []
        for page in document:
            drawings = page.get_drawings()
            has_text = bool(page.get_text("text").strip())
            pages.append((page, drawings, has_text, [] if has_text else _extract_glyphs(drawings)))
        outline = [glyph for *_, glyphs in pages for glyph in glyphs]
        em = reader.measure_em(outline) or DEFAULT_EM

        for number, (page, drawings, has_text, glyphs) in enumerate(pages, start=1):
            if has_text:
                rows = _read_text_page(page, drawings, number)
            elif glyphs:
                rows = _read_outline_page(page, drawings, glyphs, number, reader, em)
            elif page.get_images():
                raise UnsupportedPdfError(
                    "PDF berupa gambar hasil scan; dokumen seperti ini belum didukung."
                )
            else:
                rows = []
            yield from rows
            if on_page:
                on_page(number, document.page_count)
