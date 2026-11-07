# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Membaca teks dari PDF yang hurufnya berupa outline vector.

PDF DPA hasil cetak SIPD lewat "Microsoft Print to PDF" tidak punya text layer:
setiap huruf adalah satu path vector tanpa font. Karena bentuknya sama dengan
Arial, tiap path dicocokkan dengan bentuk Arial Regular/Bold. Hasilnya
deterministik, jauh lebih cepat dari OCR, dan spasinya tepat karena ditentukan
dari metrik advance font, bukan ditebak dari gambar.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

GRID = 32                   # ukuran bitmap pembanding (piksel)
SUPERSAMPLE = 4             # rasterisasi glyph sebelum diperkecil
TEMPLATE_EM = 512           # ukuran font saat membuat template
SPACE_RESIDUAL_EM = 0.13    # sisa jarak (em) yang dianggap spasi; spasi Arial = 0,278 em
METRIC_PENALTY = 2.5        # bobot selisih ukuran/posisi relatif terhadap kemiripan bentuk
DESCENDER_EM = 0.21         # kedalaman huruf menggantung Arial
CHARSET = (
    "".join(chr(c) for c in range(33, 127))
    + "".join(chr(c) for c in range(161, 256) if c != 173)
    + "–—‘’“”•…"
)
_METRICS = ("width", "height", "top", "bottom", "advance", "lsb")


class FontUnavailableError(RuntimeError):
    """Font Arial tidak ditemukan di sistem."""


@dataclass(slots=True)
class OutlineGlyph:
    """Satu path glyph dari halaman PDF, dalam satuan point."""

    x0: float
    y0: float
    x1: float
    y1: float
    bitmap_key: tuple
    polygons: list

    @property
    def is_rectangle(self) -> bool:
        return len(self.polygons) == 1 and len(self.polygons[0]) == 4


class TemplateBank:
    """Kumpulan bentuk dan metrik karakter Arial Regular + Bold."""

    def __init__(self) -> None:
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        items: list[dict] = []
        for bold, name in ((False, "arial.ttf"), (True, "arialbd.ttf")):
            path = fonts_dir / name
            if not path.exists():
                raise FontUnavailableError(f"Font tidak ditemukan: {path}")
            font = ImageFont.truetype(str(path), TEMPLATE_EM)
            items.extend(filter(None, (_render_template(font, ch, bold) for ch in CHARSET)))

        self.chars = [item["char"] for item in items]
        self.bold = np.array([item["bold"] for item in items], dtype=bool)
        self.bitmaps = np.stack([item["bitmap"] for item in items])
        self.area = self.bitmaps.sum(axis=(1, 2))
        for metric in _METRICS:
            setattr(self, metric, np.array([item[metric] for item in items], dtype=np.float32))


def _render_template(font: ImageFont.FreeTypeFont, char: str, bold: bool) -> dict | None:
    left, top, right, bottom = font.getbbox(char, anchor="ls")
    if right <= left or bottom <= top:
        return None
    pad = 4
    image = Image.new("L", (right - left + 2 * pad, bottom - top + 2 * pad), 0)
    ImageDraw.Draw(image).text((pad - left, pad - top), char, font=font, fill=255, anchor="ls")
    ink = np.array(image) > 127
    rows, cols = np.where(ink)
    if rows.size == 0:
        return None
    ink = ink[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    bitmap = Image.fromarray((ink * 255).astype(np.uint8)).resize((GRID, GRID), Image.BOX)
    return {
        "char": char,
        "bold": bold,
        "bitmap": np.array(bitmap, dtype=np.float32) / 255,
        "width": ink.shape[1] / TEMPLATE_EM,
        "height": ink.shape[0] / TEMPLATE_EM,
        "top": -(top + rows.min() - pad) / TEMPLATE_EM,
        "bottom": -(top + rows.max() + 1 - pad) / TEMPLATE_EM,
        "advance": font.getlength(char) / TEMPLATE_EM,
        "lsb": (left + cols.min() - pad) / TEMPLATE_EM,
    }


def _flatten(items: list) -> list[list[tuple[float, float]]]:
    """Ubah segmen path PyMuPDF menjadi poligon per sub-path."""
    polygons: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    last = None

    def start(point) -> None:
        nonlocal current
        if last is None or abs(point.x - last.x) + abs(point.y - last.y) > 1e-3:
            if current:
                polygons.append(current)
            current = [(point.x, point.y)]

    for item in items:
        kind = item[0]
        if kind == "re":
            r = item[1]
            polygons.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif kind == "qu":
            q = item[1]
            polygons.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
        elif kind == "l":
            start(item[1])
            current.append((item[2].x, item[2].y))
            last = item[2]
        elif kind == "c":
            p0, p1, p2, p3 = item[1:5]
            start(p0)
            for t in (0.25, 0.5, 0.75, 1.0):
                m = 1 - t
                current.append((
                    m**3 * p0.x + 3 * m * m * t * p1.x + 3 * m * t * t * p2.x + t**3 * p3.x,
                    m**3 * p0.y + 3 * m * m * t * p1.y + 3 * m * t * t * p2.y + t**3 * p3.y,
                ))
            last = p3
    if current:
        polygons.append(current)
    return polygons


def make_glyph(items: list, rect) -> OutlineGlyph:
    polygons = _flatten(items)
    key = tuple(
        (round(x - rect.x0, 2), round(y - rect.y0, 2)) for poly in polygons for x, y in poly
    )
    return OutlineGlyph(rect.x0, rect.y0, rect.x1, rect.y1, key, polygons)


def _rasterize(glyph: OutlineGlyph) -> np.ndarray:
    """Gambar glyph ke kotak GRID x GRID; lubang huruf ditangani dengan XOR."""
    size = GRID * SUPERSAMPLE
    width = max(glyph.x1 - glyph.x0, 1e-3)
    height = max(glyph.y1 - glyph.y0, 1e-3)
    canvas = None
    for polygon in glyph.polygons:
        if len(polygon) < 3:
            continue
        layer = Image.new("1", (size, size), 0)
        points = [
            ((x - glyph.x0) / width * (size - 1), (y - glyph.y0) / height * (size - 1))
            for x, y in polygon
        ]
        ImageDraw.Draw(layer).polygon(points, fill=1)
        canvas = layer if canvas is None else ImageChops.logical_xor(canvas, layer)
    if canvas is None:
        return np.zeros((GRID, GRID), dtype=np.float32)
    return np.array(canvas.convert("L").resize((GRID, GRID), Image.BOX), dtype=np.float32) / 255


class GlyphReader:
    """Mengubah deretan glyph satu baris menjadi teks."""

    def __init__(self, bank: TemplateBank | None = None) -> None:
        self.bank = bank or TemplateBank()
        self._similarity_cache: dict[tuple, np.ndarray] = {}

    def _similarity(self, glyph: OutlineGlyph) -> np.ndarray:
        """Kemiripan bentuk (IoU) glyph terhadap semua template; di-cache per bentuk."""
        cached = self._similarity_cache.get(glyph.bitmap_key)
        if cached is None:
            if len(self._similarity_cache) > 50_000:
                self._similarity_cache.clear()
            bitmap = _rasterize(glyph)
            intersection = np.minimum(bitmap, self.bank.bitmaps).sum(axis=(1, 2))
            union = bitmap.sum() + self.bank.area - intersection
            cached = (intersection + 1e-3) / (union + 1e-3)
            self._similarity_cache[glyph.bitmap_key] = cached
        return cached

    def measure_em(self, glyphs: list[OutlineGlyph]) -> float | None:
        """Ukuran font (pt) dari perbandingan tinggi glyph dengan template terdekatnya."""
        tall = [g for g in glyphs if g.y1 - g.y0 > 3][:600]
        if len(tall) < 3:
            return None
        return float(np.median([
            (g.y1 - g.y0) / self.bank.height[int(self._similarity(g).argmax())] for g in tall
        ]))

    def read_line(self, glyphs: list[OutlineGlyph], em: float) -> tuple[str, float]:
        """Kembalikan (teks, kepercayaan terendah) untuk glyph satu baris."""
        bank = self.bank
        glyphs = sorted(glyphs, key=lambda g: g.x0)
        similarity = np.stack([self._similarity(g) for g in glyphs])
        widths = np.array([[g.x1 - g.x0] for g in glyphs], dtype=np.float32) / em
        tops = np.array([[g.y0] for g in glyphs], dtype=np.float32)
        bottoms = np.array([[g.y1] for g in glyphs], dtype=np.float32)
        size_penalty = np.abs(bank.width - widths) + np.abs(bank.height - (bottoms - tops) / em)

        # Garis dasar dan ketebalan dipilih bersama: kombinasi dengan skor total
        # tertinggi. Satu baris selalu satu ketebalan.
        best_total, picks, allowed = -np.inf, None, None
        for baseline in _baseline_candidates(glyphs, em):
            position_penalty = (
                np.abs(bank.top - (baseline - tops) / em)
                + np.abs(bank.bottom - (baseline - bottoms) / em)
            )
            scores = similarity - METRIC_PENALTY * (size_penalty + position_penalty)
            for weight in (bank.bold, ~bank.bold):
                masked = np.where(weight, scores, -np.inf)
                total = float(masked.max(axis=1).sum())
                if total > best_total:
                    best_total, picks, allowed = total, masked.argmax(axis=1).tolist(), weight

        chars = [bank.chars[i] for i in picks]
        confidence = float(min(similarity[row, i] for row, i in enumerate(picks)))
        self._resolve_i_l(glyphs, picks, chars, em, allowed)

        parts: list[str] = []
        for i, char in enumerate(chars):
            if i and self._gap(glyphs[i - 1], picks[i - 1], glyphs[i], picks[i], em) > SPACE_RESIDUAL_EM:
                parts.append(" ")
            parts.append(char)
        return "".join(parts), confidence

    def _gap(self, left: OutlineGlyph, left_id: int, right: OutlineGlyph, right_id: int, em: float) -> float:
        """Jarak (em) antara posisi pena akhir glyph kiri dan pena awal glyph kanan."""
        bank = self.bank
        pen_end = left.x0 / em - bank.lsb[left_id] + bank.advance[left_id]
        pen_start = right.x0 / em - bank.lsb[right_id]
        return float(pen_start - pen_end)

    def _resolve_i_l(self, glyphs, picks, chars, em, allowed) -> None:
        """Bedakan I dan l yang bentuknya nyaris identik.

        Di Arial Regular lebar advance keduanya berbeda, jadi dipilih yang paling
        pas dengan posisi huruf tetangga. Di Arial Bold metriknya sama, sehingga
        dipakai konteks huruf di sekitarnya.
        """
        bank = self.bank
        for i, char in enumerate(chars):
            if char not in ("I", "l"):
                continue
            candidates = {
                c: next(j for j, ch in enumerate(bank.chars) if ch == c and allowed[j])
                for c in ("I", "l")
            }
            fit = {}
            for candidate, index in candidates.items():
                residuals = []
                if i:
                    residuals.append(self._gap(glyphs[i - 1], picks[i - 1], glyphs[i], index, em))
                if i + 1 < len(chars):
                    residuals.append(self._gap(glyphs[i], index, glyphs[i + 1], picks[i + 1], em))
                touching = [abs(r) for r in residuals if abs(r) < SPACE_RESIDUAL_EM]
                fit[candidate] = sum(touching) / len(touching) if touching else 0.0
            if abs(fit["I"] - fit["l"]) > 0.012:
                best = min(fit, key=fit.get)
            else:
                best = self._i_l_by_context(glyphs, picks, chars, i, em)
            chars[i] = best
            picks[i] = candidates[best]

    def _i_l_by_context(self, glyphs, picks, chars, i, em) -> str:
        def adjacent(step: int) -> str:
            j = i + step
            if not 0 <= j < len(chars):
                return ""
            a, b = (j, i) if step < 0 else (i, j)
            return "" if self._gap(glyphs[a], picks[a], glyphs[b], picks[b], em) > SPACE_RESIDUAL_EM else chars[j]

        before, after = adjacent(-1), adjacent(1)
        if before.isalpha():
            if before.islower():
                return "l"
            return "I" if after.isupper() or not after else "l"
        if after.isupper():
            return "I"
        # Awal kata diikuti huruf kecil: "lain", "lokasi" vs "Industri", "Iuran".
        if after in ("a", "e", "i", "o"):
            return "l"
        if after == "u":
            return "I" if i + 2 < len(chars) and chars[i + 2] == "r" else "l"
        return "I"


def _baseline_candidates(glyphs: list[OutlineGlyph], em: float) -> set[float]:
    """Garis dasar selalu berada di dasar salah satu glyph, kecuali semuanya menggantung."""
    candidates = {round(g.y1, 1) for g in glyphs}
    candidates.add(round(max(g.y1 for g in glyphs) - DESCENDER_EM * em, 1))
    return candidates
