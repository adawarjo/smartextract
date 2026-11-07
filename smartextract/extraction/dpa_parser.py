# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 adawarjo
"""Mengubah baris tabel PDF DPA menjadi data rekening belanja.

Dua jenis dokumen didukung. DPA Penetapan punya satu nominal per rekening.
DPPA (parsial/perubahan) punya tiga: Sebelum, Setelah, dan Bertambah/Berkurang,
dengan pagu mengikuti nilai Setelah.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable

from .glyph_reader import GlyphReader
from .pdf_table import TableRow, UnsupportedPdfError, read_table_rows

MIN_CONFIDENCE = 0.75   # teks Arial terbaca >= 0,80; font lain jatuh ke 0,5-0,7

_KEGIATAN = re.compile(r"^Kegiatan\s*:\s*([\d.]+)\s*-\s*(.+)$")
_SUB_KEGIATAN = re.compile(r"^Sub Kegiatan\s*:\s*([\d.]+)\s*-\s*(.+)$")
_SUMBER_PENDANAAN = re.compile(r"^Sumber Pendanaan\s*:\s*(.+)$")
_SUMBER_DANA = re.compile(r"Sumber Dana\s*:\s*(.*)$")
_TOTAL_SUB = "Jumlah Anggaran Sub Kegiatan"
_NOMOR_DOKUMEN = re.compile(r"^Nomor (DPP?A)\b")
_RUPIAH = re.compile(r"Rp[\d.,]+")
_PEMENGGAL_KATA = re.compile(r"\w[-/]$")
_KODE_REKENING = re.compile(r"^\d+(?:\.\d+){5}$")
_NOMINAL = re.compile(r"^Rp\s?((?:\d{1,3}(?:\.\d{3})+)|\d+)(?:,(\d{1,2}))?$")

_KATA_KECIL = {
    "dan", "atau", "di", "ke", "dari", "yang", "untuk", "pada", "dengan", "serta", "oleh", "bagi",
}
_SINGKATAN = {
    "APBD", "ASN", "BLUD", "BUMD", "BUMN", "DPRD", "OPD", "PAD", "PKK", "PNS", "SDA", "SDM",
    "SKPD", "TIK", "UMKM", "UPTD",
}
_ANGKA_ROMAWI = re.compile(r"^(?:I{1,3}|IV|VI{0,3}|IX|X)$")


@dataclass(frozen=True)
class JenisDokumen:
    """Perbedaan antar-jenis dokumen DPA yang memengaruhi pembacaan."""

    nama: str
    menu: str
    nomor: str          # kata setelah "Nomor" di baris pertama dokumen
    perubahan: bool     # nominal berupa Sebelum, Setelah, Bertambah/Berkurang

    @property
    def kolom_nominal(self) -> int:
        return 3 if self.perubahan else 1

    @property
    def kolom_pagu(self) -> int:
        return 1 if self.perubahan else 0


PENETAPAN = JenisDokumen("DPA Penetapan", "Extract DPA Penetapan", "DPA", False)
PERUBAHAN = JenisDokumen("DPPA", "Extract DPA Parsial/Perubahan", "DPPA", True)


@dataclass(slots=True)
class RekeningRow:
    """Satu baris hasil; nama field sama dengan kolom template."""

    kode_kegiatan: str
    nama_kegiatan: str
    kode_sub_kegiatan: str
    nama_sub_kegiatan: str
    kode_rekening: str
    nama_rekening: str
    pagu: Decimal
    sumber_dana: str
    keterangan: str = ""
    sumber_file: str = ""
    bermasalah: bool = False


@dataclass(slots=True)
class Temuan:
    """Hasil pemeriksaan.

    Level "error" berarti data tidak bisa dipercaya, "warning" perlu diperiksa,
    dan "info" hanya catatan tentang perlakuan normal.
    """

    level: str
    pesan: str


@dataclass(slots=True)
class HasilDokumen:
    path: Path
    rows: list[RekeningRow] = field(default_factory=list)
    temuan: list[Temuan] = field(default_factory=list)
    halaman: int = 0
    detik: float = 0.0
    gagal: bool = False
    tahap: str = ""

    @property
    def total(self) -> Decimal:
        return sum((row.pagu for row in self.rows), Decimal(0))

    @property
    def jumlah_sub_kegiatan(self) -> int:
        return len({row.kode_sub_kegiatan for row in self.rows})

    @property
    def masalah(self) -> list[Temuan]:
        return [item for item in self.temuan if item.level != "info"]


def format_rupiah(value: Decimal) -> str:
    """Decimal 1450000 menjadi `Rp1.450.000`; sen hanya ditulis bila ada."""
    tanda = "-" if value < 0 else ""
    value = abs(value)
    text = f"{value:,.0f}" if value == value.to_integral_value() else f"{value:,.2f}"
    return f"{tanda}Rp" + text.replace(",", "#").replace(".", ",").replace("#", ".")


def parse_nominal(text: str) -> Decimal | None:
    """`Rp1.450.000,00` menjadi 1450000, `( Rp1.500,00 )` menjadi -1500; None bila bukan nominal."""
    text = text.strip()
    negatif = text.startswith("(") and text.endswith(")")
    match = _NOMINAL.match(text[1:-1].strip() if negatif else text)
    if not match:
        return None
    value = Decimal(f"{match.group(1).replace('.', '')}.{match.group(2) or '0'}")
    return -value if negatif else value


def gabung_baris(bagian: Iterable[str]) -> str:
    """Satukan teks yang terbungkus ke beberapa baris.

    Browser bisa memenggal tepat setelah `-` atau `/` yang menempel pada kata
    (`Bidang-` lalu `Keuangan`); di situ teks aslinya tidak berspasi. PDF tidak
    menyimpan bedanya dengan `Kantor- Kertas` yang kebetulan terpenggal di tempat
    yang sama, jadi kasus tersebut ikut tersambung tanpa spasi.
    """
    hasil = ""
    for teks in bagian:
        if hasil and not _PEMENGGAL_KATA.search(hasil):
            hasil += " "
        hasil += teks
    return hasil


def rapikan_nama(text: str) -> str:
    """Teks HURUF BESAR dijadikan format judul; teks lain dibiarkan apa adanya."""
    if not text.isupper():
        return text

    words = re.findall(r"[^\W\d_]+|\d+|[^\w]+|_", text)
    pertama = True

    def ubah(word: str) -> str:
        nonlocal pertama
        if not word[0].isalpha():
            return word
        lower = word.lower()
        if word in _SINGKATAN or _ANGKA_ROMAWI.match(word):
            result = word
        elif lower in _KATA_KECIL and not pertama:
            result = lower
        else:
            result = lower.capitalize()
        pertama = False
        return result

    return "".join(ubah(word) for word in words)


@dataclass(slots=True)
class _Rekening:
    kode: str
    nama: str
    nominal: list[Decimal | None]
    jumlah: Decimal | None
    halaman: int
    keyakinan: float
    per_sumber: dict[str, Decimal] = field(default_factory=dict)


@dataclass(slots=True)
class _SubKegiatan:
    kode: str
    nama: str
    sumber_pendanaan: str = ""
    total_tercetak: Decimal | None = None
    total_sebelum: Decimal | None = None
    rekening: list[_Rekening] = field(default_factory=list)


def _nilai_header(row: TableRow) -> str:
    """Isi baris header; lanjutan teks yang terbungkus digabung dengan spasi."""
    return gabung_baris(line.text for line in row.lines)


def _baca_rekening(row: TableRow, jenis: JenisDokumen) -> _Rekening | None:
    lines = row.lines
    if not lines or not _KODE_REKENING.match(lines[0].text):
        return None
    jumlah_kolom = jenis.kolom_nominal
    akhir = lines[-jumlah_kolom:] if len(lines) > jumlah_kolom else []
    nominal = [parse_nominal(line.text) for line in akhir] or [None] * jumlah_kolom
    return _Rekening(
        kode=lines[0].text,
        nama=gabung_baris(line.text for line in lines[1:-jumlah_kolom]),
        nominal=nominal,
        jumlah=nominal[jenis.kolom_pagu],
        halaman=row.page,
        keyakinan=min(line.confidence for line in lines),
    )


def _baca_sumber_dana(row: TableRow, jenis: JenisDokumen) -> tuple[str, Decimal | None] | None:
    """Baris `[ # ] ... / Sumber Dana: ...` beserta jumlahnya."""
    lines = row.lines
    if not lines or not lines[0].text.startswith("[ #"):
        return None
    nominal = [parse_nominal(line.text) for line in lines[-jenis.kolom_nominal:]]
    lengkap = len(nominal) == jenis.kolom_nominal and None not in nominal
    jumlah = nominal[jenis.kolom_pagu] if lengkap else None
    uraian = [line.text for line in (lines[:-jenis.kolom_nominal] if lengkap else lines)]
    for index, text in enumerate(uraian):
        match = _SUMBER_DANA.search(text)
        if match:
            return gabung_baris([match.group(1), *uraian[index + 1:]]).strip(), jumlah
    return "", jumlah


def parse_rows(
    rows: Iterable[TableRow],
    sumber_file: str = "",
    jenis: JenisDokumen = PENETAPAN,
) -> tuple[list[RekeningRow], list[Temuan]]:
    """Susun baris tabel menjadi rekening, lalu cocokkan dengan total tercetak."""
    kegiatan: tuple[str, str] | None = None
    sub_list: list[tuple[tuple[str, str] | None, _SubKegiatan]] = []
    sub: _SubKegiatan | None = None
    rekening: _Rekening | None = None
    menunggu_sub = True

    for row in rows:
        header = _nilai_header(row)
        if match := _NOMOR_DOKUMEN.match(header):
            # Tanpa pemeriksaan ini, kolom nominal dokumen lain akan salah terbaca.
            if match.group(1) != jenis.nomor:
                lain = PERUBAHAN if jenis is PENETAPAN else PENETAPAN
                return [], [Temuan("error", f"Dokumen ini {lain.nama}; gunakan menu {lain.menu}.")]
        elif match := _KEGIATAN.match(header):
            kegiatan = (match.group(1), rapikan_nama(match.group(2).strip()))
        elif match := _SUB_KEGIATAN.match(header):
            sub = _SubKegiatan(match.group(1), rapikan_nama(match.group(2).strip()))
            sub_list.append((kegiatan, sub))
            rekening = None
            menunggu_sub = False
        elif menunggu_sub:
            continue
        elif match := _SUMBER_PENDANAAN.match(header):
            sub.sumber_pendanaan = match.group(1).strip()
        elif header.startswith(_TOTAL_SUB):
            nilai = [parse_nominal(text) for text in _RUPIAH.findall(header)]
            sub.total_tercetak = nilai[-1] if nilai else None
            sub.total_sebelum = nilai[0] if jenis.perubahan and len(nilai) == 2 else None
            rekening = None
            menunggu_sub = True
        elif baru := _baca_rekening(row, jenis):
            rekening = baru
            sub.rekening.append(rekening)
        elif rekening is not None and (sumber := _baca_sumber_dana(row, jenis)):
            nama_sumber, jumlah = sumber
            nama_sumber = nama_sumber or sub.sumber_pendanaan
            rekening.per_sumber[nama_sumber] = (
                rekening.per_sumber.get(nama_sumber, Decimal(0)) + (jumlah or Decimal(0))
            )

    hasil: list[RekeningRow] = []
    temuan: list[Temuan] = []
    if not sub_list:
        temuan.append(Temuan("error", "Baris 'Sub Kegiatan' tidak ditemukan; ini bukan format DPA yang dikenali."))
    for kegiatan_sub, item in sub_list:
        _susun_sub_kegiatan(kegiatan_sub, item, sumber_file, jenis, hasil, temuan)
    return hasil, temuan


def _susun_sub_kegiatan(kegiatan, sub: _SubKegiatan, sumber_file, jenis, hasil, temuan) -> None:
    kode_kegiatan, nama_kegiatan = kegiatan or ("", "")
    if kegiatan is None:
        temuan.append(Temuan("error", f"{sub.kode}: baris 'Kegiatan' tidak ditemukan."))
    if not sub.rekening:
        temuan.append(Temuan("error", f"{sub.kode}: tidak ada rekening belanja yang terbaca."))
        return

    awal = len(hasil)
    dihapus: list[str] = []
    for rekening in sub.rekening:
        bermasalah = False
        lokasi = f"{sub.kode} / {rekening.kode} (hal. {rekening.halaman})"
        if None in rekening.nominal:
            temuan.append(Temuan("error", f"{lokasi}: nominal rekening tidak terbaca."))
            bermasalah = True
        elif jenis.perubahan:
            sebelum, setelah, selisih = rekening.nominal
            if setelah - sebelum != selisih:
                temuan.append(Temuan("error", f"{lokasi}: selisih Sebelum dan Setelah tidak sama dengan Bertambah/Berkurang {format_rupiah(selisih)}."))
                bermasalah = True
        if rekening.keyakinan < MIN_CONFIDENCE:
            temuan.append(Temuan("warning", f"{lokasi}: bentuk huruf tidak yakin, mohon periksa manual."))
            bermasalah = True

        per_sumber = dict(rekening.per_sumber)
        if not per_sumber:
            per_sumber = {sub.sumber_pendanaan: rekening.jumlah or Decimal(0)}
            temuan.append(Temuan("warning", f"{lokasi}: sumber dana rekening tidak ditemukan, memakai sumber dana sub kegiatan."))
            bermasalah = True
        elif rekening.jumlah is not None and sum(per_sumber.values()) != rekening.jumlah:
            temuan.append(Temuan("error", f"{lokasi}: jumlah per sumber dana {format_rupiah(sum(per_sumber.values()))} tidak sama dengan nilai rekening {format_rupiah(rekening.jumlah)}."))
            bermasalah = True

        if jenis.perubahan and rekening.jumlah == 0:
            dihapus.append(rekening.kode)
        for sumber, pagu in per_sumber.items():
            if jenis.perubahan and pagu == 0:
                continue
            hasil.append(RekeningRow(
                kode_kegiatan, nama_kegiatan, sub.kode, sub.nama, rekening.kode, rekening.nama,
                pagu, sumber, sumber_file=sumber_file, bermasalah=bermasalah,
            ))

    if dihapus:
        temuan.append(Temuan("info", f"{sub.kode}: {len(dihapus)} rekening bernilai Rp0 setelah perubahan tidak disertakan: {', '.join(dihapus)}."))

    total = sum((row.pagu for row in hasil[awal:]), Decimal(0))
    if sub.total_tercetak is None:
        temuan.append(Temuan("warning", f"{sub.kode}: 'Jumlah Anggaran Sub Kegiatan' tidak ditemukan, total tidak bisa dicocokkan."))
    elif sub.total_tercetak != total:
        temuan.append(Temuan("error", f"{sub.kode}: jumlah rekening {format_rupiah(total)} tidak sama dengan total dokumen {format_rupiah(sub.total_tercetak)}."))

    if sub.total_sebelum is not None:
        sebelum = sum((r.nominal[0] or Decimal(0) for r in sub.rekening), Decimal(0))
        if sebelum != sub.total_sebelum:
            temuan.append(Temuan("error", f"{sub.kode}: jumlah nilai Sebelum {format_rupiah(sebelum)} tidak sama dengan total dokumen {format_rupiah(sub.total_sebelum)}."))


def extract_document(
    path: Path,
    reader: GlyphReader,
    on_page: Callable[[int, int], None] | None = None,
    jenis: JenisDokumen = PENETAPAN,
) -> HasilDokumen:
    """Ekstrak satu PDF. Kegagalan dicatat di hasil, bukan dilempar sebagai exception."""
    hasil = HasilDokumen(path=path)
    started = time.perf_counter()

    def progress(page: int, total: int) -> None:
        hasil.halaman = total
        if on_page:
            on_page(page, total)

    try:
        table_rows = list(read_table_rows(path, reader, progress))
        hasil.rows, hasil.temuan = parse_rows(table_rows, path.name, jenis)
    except UnsupportedPdfError as error:
        hasil.temuan.append(Temuan("error", str(error)))
    except Exception as error:  # PDF rusak: satu file gagal tak boleh menghentikan batch
        hasil.temuan.append(Temuan("error", f"Gagal membaca PDF: {error}"))
    hasil.gagal = any(item.level == "error" for item in hasil.temuan) and not hasil.rows
    hasil.detik = time.perf_counter() - started
    return hasil


def _kunci_rekening(row: RekeningRow) -> tuple:
    return row.kode_sub_kegiatan, row.kode_rekening, row.sumber_dana


def tandai_duplikat(hasil_list: list[HasilDokumen], kunci: Callable = _kunci_rekening) -> None:
    """Tandai rekening yang muncul di lebih dari satu file (mis. file yang sama dua kali)."""
    pemilik: dict[tuple, str] = {}
    for hasil in hasil_list:
        kembar: Counter[str] = Counter()
        for row in hasil.rows:
            asal = pemilik.setdefault(kunci(row), hasil.path.name)
            if asal != hasil.path.name:
                row.bermasalah = True
                kembar[asal] += 1
        for asal, jumlah in kembar.items():
            hasil.temuan.append(Temuan("warning", f"{jumlah} rekening sudah ada di file {asal}."))
