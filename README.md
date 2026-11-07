# SmartExtract

Aplikasi desktop Windows untuk mengambil data anggaran dari dokumen SIPD ke CSV dan Excel,
lalu mencocokkannya dengan total yang tercetak di dokumen.

## Unduh

**[Unduh SmartExtract.exe](https://github.com/adawarjo/smartextract/raw/main/dist/SmartExtract.exe)**
(versi 1.3.2, 50 MB)

Cukup satu file ini, tanpa instalasi dan tanpa Python. Aplikasi berjalan di Windows 64-bit dan
diuji di Windows 11. Panduan lengkapnya ada di [readme.txt](readme.txt).

## Menu

| Menu | Sumber | Hasil per rekening |
|---|---|---|
| Extract DPA Penetapan | PDF DPA Rincian Belanja SKPD | Pagu dan sumber dana |
| Extract DPA Parsial/Perubahan | PDF DPPA Rincian Belanja SKPD | Pagu nilai Setelah dan sumber dana |
| Extract RAK Penetapan/Parsial/Perubahan | Excel RAK Belanja | Pagu dan nilai Januari sampai Desember |

Banyak file bisa diproses sekaligus dan digabung menjadi satu hasil. Hasil bisa disimpan ke CSV
atau Excel.

## Cara memakai

1. Buka `SmartExtract.exe`. Jendela muncul setelah beberapa detik.
2. Pilih menu sesuai jenis dokumen.
3. Pilih **Folder** atau **File** sumber, lalu klik **Mulai Ekstraksi**.
4. Periksa kartu **Validasi** dan tab **Status File**.
5. Klik **Simpan CSV** atau **Simpan Excel**.

Di menu RAK, tombol **Folder** hanya mengambil file berawalan `RAK_` dengan akhiran `.xlsx`. File
dengan nama lain bisa dipilih lewat tombol **File**.

## Format hasil

**Menu DPA:** `kode_kegiatan`, `nama_kegiatan`, `kode_sub_kegiatan`, `nama_sub_kegiatan`,
`kode_rekening`, `nama_rekening`, `pagu`, `sumber_dana`, `keterangan`

**Menu RAK:** `kode_sub_kegiatan`, `kode_rekening`, `nama_rekening`, `pagu`, `jan` sampai `des`

File CSV memakai encoding UTF-8 dengan BOM dan pemisah titik koma.

## Pemeriksaan otomatis

Setiap hasil dicocokkan dengan total yang tercetak di dokumen:

- **DPA:** jumlah pagu dengan `Jumlah Anggaran Sub Kegiatan`, dan nilai rekening dengan jumlah per
  sumber dana. Pada DPPA, selisih Sebelum dan Setelah juga dicocokkan dengan nilai
  Bertambah/Berkurang.
- **RAK:** Anggaran, Total RAK, dan jumlah 12 bulan tiap rekening, total tiap bulan, serta
  Nilai Anggaran.

Baris yang bermasalah ditandai kuning dan tetap ikut tersimpan, jadi periksa tab **Status File**
sebelum memakai datanya. File yang gagal dibaca tidak ikut tersimpan.

## Batasan

- PDF hasil scan belum didukung.
- Rekening dengan dua sumber dana baru diuji dengan data buatan.
- Excel RAK tahap Penetapan dan Parsial yang asli belum pernah diuji; pengujian dengan file asli
  baru memakai tahap Perubahan.
- Nama yang terpotong ke baris baru tepat setelah `-` atau `/` disambung tanpa spasi, karena PDF
  tidak menyimpan bedanya. Periksa nama seperti `Kantor- Kertas` di hasil Anda.

## Peringatan saat dibuka

Exe ini belum ditandatangani secara digital, jadi Windows SmartScreen bisa menampilkan `Windows
protected your PC`, dan antivirus kadang keliru menandainya. Bila Anda memercayai sumbernya, klik
**More info** lalu **Run anyway**.

## Disclaimer

Hasil ekstraksi dibaca otomatis dari PDF dan dapat mengandung kesalahan. Periksa hasilnya dengan
dokumen asli sebelum digunakan.

Aplikasi ini disediakan apa adanya, tanpa jaminan apa pun. Pembuat tidak bertanggung jawab atas
kerugian yang timbul dari penggunaan aplikasi ini.

Aplikasi ini bukan bagian dari SIPD. Dokumen asli tetap menjadi acuan resmi.

## Kode sumber

Kode sumber aplikasi ada di repo ini. Untuk menjalankannya dibutuhkan Python 3.12 di Windows:

```
pip install -r requirements.txt
python app.py
```

Untuk membuat exe sendiri, klik dua kali `build_exe.bat`. Hasilnya ada di
`dist\SmartExtract.exe`.

- `smartextract/extraction`: pembaca PDF dan Excel, validasi, dan penulisan hasil.
- `smartextract/ui`: tampilan aplikasi.

Tes otomatis tidak disertakan karena memakai data dari dokumen anggaran asli.

## Lisensi

Copyright (c) 2026 adawarjo

SmartExtract adalah perangkat lunak bebas di bawah
[GNU Affero General Public License versi 3](LICENSE.txt) (`AGPL-3.0-only`). Ringkasnya, Anda
boleh memakai, mengubah, dan menyebarkannya, selama versi yang Anda sebarkan juga menyertakan
kode sumbernya di bawah lisensi yang sama. Ketentuan lengkapnya ada di `LICENSE.txt`.

Komponen pihak ketiga yang dibundel di dalam exe, dengan teks lisensi lengkap di
[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt):

| Komponen | Lisensi |
|---|---|
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 |
| [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) | MIT |
| [NumPy](https://numpy.org) | BSD-3-Clause |
| [openpyxl](https://openpyxl.readthedocs.io) | MIT |
| [Pillow](https://python-pillow.org) | MIT-CMU |
