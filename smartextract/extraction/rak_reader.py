# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Membaca Excel Rencana Anggaran Kas (RAK Belanja) unduhan SIPD.

Formatnya sama untuk tahap Penetapan, Parsial, dan Perubahan. Kolom dan baris dicari
dari judulnya, bukan dari posisi sel, supaya tahan terhadap pergeseran tata letak.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .dpa_parser import HasilDokumen, Temuan, format_rupiah

BULAN = ("jan", "feb", "mar", "apr", "mei", "jun", "jul", "agu", "sep", "okt", "nov", "des")
_NAMA_BULAN = (
    "januari", "februari", "maret", "april", "mei", "juni",
    "juli", "agustus", "september", "oktober", "november", "desember",
)
_KODE_REKENING = re.compile(r"^\d+(?:\.\d+){5}$")
_KODE_NAMA = re.compile(r"^([\d.]+)\s*-\s*(.+)$")
_BARIS_TAHUN = re.compile(r"^TAHUN\s+\d{4}$")
_KATA_TAHAP = ("APBD", "PENETAPAN", "PERUBAHAN", "PERGESERAN", "PARSIAL")
_JUDUL_TOTAL_BULAN = "JUMLAH ALOKASI KAS YANG TERSEDIA DARI BELANJA PER BULAN"


class FormatRakError(ValueError):
    """Isi file bukan RAK Belanja yang dikenali."""


@dataclass(slots=True)
class KasRow:
    """Satu baris hasil; nama field sama dengan kolom template."""

    kode_sub_kegiatan: str
    nama_sub_kegiatan: str
    kode_rekening: str
    nama_rekening: str
    pagu: Decimal
    jan: Decimal
    feb: Decimal
    mar: Decimal
    apr: Decimal
    mei: Decimal
    jun: Decimal
    jul: Decimal
    agu: Decimal
    sep: Decimal
    okt: Decimal
    nov: Decimal
    des: Decimal
    sumber_file: str = ""
    bermasalah: bool = False


@dataclass(slots=True)
class _Kolom:
    anggaran: int
    total_rak: int
    bulan: list[int]
    data_mulai: int


def _teks(value) -> str:
    return "" if value is None else str(value).strip()


def _angka(value) -> Decimal | None:
    """Sel kosong berarti 0; teks yang bukan angka menghasilkan None."""
    if value is None:
        return Decimal(0)
    if isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        return None


def _baca_tahap(judul: str) -> str:
    """Tahap dokumen tertulis tepat di atas baris `TAHUN 2026` pada judul."""
    lines = [line.strip().upper() for line in judul.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if index and _BARIS_TAHUN.match(line) and any(kata in lines[index - 1] for kata in _KATA_TAHAP):
            return lines[index - 1]
    return ""


def _cari_lembar(workbook) -> tuple[list[list], int]:
    """Lembar RAK Belanja beserta nomor baris judul tabelnya."""
    for sheet in workbook.worksheets:
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
        pengenal = " ".join(_teks(value).upper() for value in (rows[0] if rows else []))
        if "RAK BELANJA" not in pengenal and "RAK BELANJA" not in sheet.title.upper():
            continue
        for index, row in enumerate(rows):
            if row and _teks(row[0]).lower() == "kode rekening":
                return rows, index
    raise FormatRakError("Bukan file RAK Belanja yang dikenali.")


def _cari_kolom(rows: list[list], baris_judul: int) -> _Kolom:
    judul = [_teks(value).lower() for value in rows[baris_judul]]
    baris_bulan = next(
        (i for i, row in enumerate(rows[baris_judul:], baris_judul)
         if "januari" in [_teks(value).lower() for value in row]),
        None,
    )
    if baris_bulan is None or "anggaran tahun ini" not in judul or "total rak" not in judul:
        raise FormatRakError("Kolom Anggaran, Total RAK, atau bulan tidak ditemukan.")
    nama = [_teks(value).lower() for value in rows[baris_bulan]]
    if any(bulan not in nama for bulan in _NAMA_BULAN):
        raise FormatRakError("Kolom bulan tidak lengkap.")
    return _Kolom(
        judul.index("anggaran tahun ini"),
        judul.index("total rak"),
        [nama.index(bulan) for bulan in _NAMA_BULAN],
        baris_bulan + 1,
    )


def _nilai_label(rows: list[list], baris_judul: int) -> dict[str, object]:
    """Pasangan label-nilai di atas tabel, mis. `Sub Kegiatan` dan `Nilai Anggaran`."""
    hasil: dict[str, object] = {}
    for row in rows[:baris_judul]:
        if len(row) > 1:
            hasil[_teks(row[0]).lower()] = row[1]
    return hasil


def _baca_lembar(rows: list[list], baris_judul: int, hasil: HasilDokumen) -> None:
    kolom = _cari_kolom(rows, baris_judul)
    label = _nilai_label(rows, baris_judul)
    sub_kegiatan = _KODE_NAMA.match(_teks(label.get("sub kegiatan")))
    if not sub_kegiatan:
        raise FormatRakError("Baris Sub Kegiatan tidak ditemukan.")
    kode_sub, nama_sub = sub_kegiatan.group(1), sub_kegiatan.group(2).strip()
    hasil.tahap = _baca_tahap(_teks(rows[0][0]))

    jumlah = [Decimal(0)] * 12
    total_anggaran = Decimal(0)
    total_tercetak: list[Decimal | None] | None = None
    nol: list[str] = []

    def lapor(level: str, pesan: str) -> None:
        hasil.temuan.append(Temuan(level, f"{kode_sub} / {pesan}"))

    for row in rows[kolom.data_mulai:]:
        row = row + [None] * (kolom.total_rak + 14 - len(row))
        kode = _teks(row[0])
        if kode.upper() == _JUDUL_TOTAL_BULAN:
            total_tercetak = [_angka(row[index]) for index in kolom.bulan]
            continue
        if not _KODE_REKENING.match(kode):
            continue

        nama = _teks(row[1])
        anggaran = _angka(row[kolom.anggaran])
        total_rak = _angka(row[kolom.total_rak])
        bulan = [_angka(row[index]) for index in kolom.bulan]
        if anggaran is None or total_rak is None or None in bulan:
            lapor("error", f"{kode}: ada nilai yang bukan angka; rekening ini dilewati.")
            continue
        if anggaran == 0 and total_rak == 0 and not any(bulan):
            nol.append(kode)
            continue

        bermasalah = False
        if anggaran != total_rak:
            lapor("error", f"{kode}: Anggaran {format_rupiah(anggaran)} tidak sama dengan Total RAK {format_rupiah(total_rak)}.")
            bermasalah = True
        if sum(bulan) != total_rak:
            lapor("error", f"{kode}: jumlah 12 bulan {format_rupiah(sum(bulan))} tidak sama dengan Total RAK {format_rupiah(total_rak)}.")
            bermasalah = True

        hasil.rows.append(KasRow(
            kode_sub, nama_sub, kode, nama, anggaran, *bulan,
            sumber_file=hasil.path.name, bermasalah=bermasalah,
        ))
        total_anggaran += anggaran
        jumlah = [a + b for a, b in zip(jumlah, bulan)]

    if not hasil.rows and not nol:
        raise FormatRakError("Tidak ada rekening belanja yang terbaca.")
    if nol:
        hasil.temuan.append(Temuan(
            "info", f"{kode_sub}: {len(nol)} rekening bernilai Rp0 tidak disertakan: {', '.join(nol)}.",
        ))

    nilai_anggaran = _angka(label.get("nilai anggaran"))
    if label.get("nilai anggaran") is None:
        hasil.temuan.append(Temuan("warning", f"{kode_sub}: Nilai Anggaran tidak ditemukan, total tidak bisa dicocokkan."))
    elif nilai_anggaran != total_anggaran:
        hasil.temuan.append(Temuan(
            "error",
            f"{kode_sub}: jumlah rekening {format_rupiah(total_anggaran)} tidak sama dengan "
            f"Nilai Anggaran {format_rupiah(nilai_anggaran or Decimal(0))}.",
        ))

    if total_tercetak is None:
        hasil.temuan.append(Temuan("warning", f"{kode_sub}: baris jumlah per bulan tidak ditemukan, total bulan tidak bisa dicocokkan."))
        return
    for nama_bulan, terhitung, tercetak in zip(_NAMA_BULAN, jumlah, total_tercetak):
        if terhitung != tercetak:
            hasil.temuan.append(Temuan(
                "error",
                f"{kode_sub}: jumlah {nama_bulan.capitalize()} {format_rupiah(terhitung)} tidak sama "
                f"dengan total dokumen {format_rupiah(tercetak or Decimal(0))}.",
            ))


def extract_rak(path: Path) -> HasilDokumen:
    """Ekstrak satu file. Kegagalan dicatat di hasil, bukan dilempar sebagai exception."""
    hasil = HasilDokumen(path=path)
    started = time.perf_counter()
    try:
        workbook = load_workbook(path, data_only=True)
        rows, baris_judul = _cari_lembar(workbook)
        _baca_lembar(rows, baris_judul, hasil)
    except FormatRakError as error:
        hasil.temuan.append(Temuan("error", str(error)))
    except InvalidFileException:
        hasil.temuan.append(Temuan("error", "Format file tidak didukung; simpan sebagai .xlsx."))
    except (BadZipFile, KeyError, OSError):
        hasil.temuan.append(Temuan("error", "File rusak atau bukan Excel."))
    except Exception as error:  # satu file gagal tak boleh menghentikan batch
        hasil.temuan.append(Temuan("error", f"Gagal membaca Excel: {error}"))
    hasil.gagal = any(item.level == "error" for item in hasil.temuan) and not hasil.rows
    hasil.detik = time.perf_counter() - started
    return hasil


def periksa_tahap(hasil_list: Iterable[HasilDokumen]) -> None:
    """Satu hasil seharusnya satu tahap; RAK Penetapan dan Perubahan jangan tercampur."""
    terbaca = [hasil for hasil in hasil_list if hasil.tahap]
    if len({hasil.tahap for hasil in terbaca}) < 2:
        return
    utama = Counter(hasil.tahap for hasil in terbaca).most_common(1)[0][0]
    for hasil in terbaca:
        if hasil.tahap != utama:
            hasil.temuan.append(Temuan(
                "warning", f"Tahap dokumen {hasil.tahap} berbeda dari file lain ({utama}).",
            ))
