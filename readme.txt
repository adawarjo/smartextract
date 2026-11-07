================================================================================
SMARTEXTRACT versi 1.3.2
Aplikasi ekstraksi data dokumen anggaran dari PDF dan Excel SIPD
================================================================================

DAFTAR ISI
  1. Tentang aplikasi
  2. Kebutuhan
  3. Memasang dan membuka aplikasi
  4. Cara memakai
  5. Format hasil
  6. Arti hasil validasi
  7. Batasan
  8. Masalah yang sering terjadi
  9. Disclaimer
 10. Lisensi


1. TENTANG APLIKASI
--------------------------------------------------------------------------------
Aplikasi ini mengambil data rekening belanja dari dokumen SIPD, mencocokkannya
dengan total yang tercetak di dokumen, lalu menyimpannya ke CSV atau Excel.

Menu yang tersedia:

  Extract DPA Penetapan
      Untuk PDF DPA Rincian Belanja SKPD.

  Extract DPA Parsial/Perubahan
      Untuk PDF DPPA Rincian Belanja SKPD.

  Extract RAK Penetapan/Parsial/Perubahan
      Untuk Excel RAK Belanja semua tahap, dengan nilai per bulan.

  About
      Menampilkan nama aplikasi, versi, pembuat, dan disclaimer.


2. KEBUTUHAN
--------------------------------------------------------------------------------
- Windows 64-bit (diuji di Windows 11)
- Tidak perlu Python dan tidak perlu instalasi


3. MEMASANG DAN MEMBUKA APLIKASI
--------------------------------------------------------------------------------
Salin SmartExtract.exe ke komputer Anda, lalu klik dua kali.

Jendela muncul setelah beberapa detik karena isi exe dibongkar dulu ke folder
sementara, jadi tidak perlu diklik berulang.


4. CARA MEMAKAI
--------------------------------------------------------------------------------
Semua menu ekstraksi dipakai dengan cara yang sama.

Langkah 1: Buka menu sesuai jenis dokumen
  PDF yang tidak sesuai dengan menu akan ditolak dan aplikasi menyebutkan menu
  yang benar.

Langkah 2: Pilih sumber
  - Tombol Folder : memproses semua file sumber di dalam satu folder.
                    Subfolder tidak ikut diproses. Menu RAK hanya mengambil
                    file berawalan RAK_ dengan akhiran .xlsx.
  - Tombol File   : memilih satu atau beberapa file tertentu.

Langkah 3: Klik Mulai Ekstraksi
  Semua file digabung menjadi satu hasil, urut nama file. Tombol berubah
  menjadi Batalkan selama proses berjalan. Bila dibatalkan, file yang sudah
  selesai tetap tampil di hasil dan bisa disimpan.

Langkah 4: Periksa hasil
  - Kartu Validasi menunjukkan ringkasan pemeriksaan.
  - Tab Hasil Ekstraksi menampilkan rekening per kegiatan dan sub kegiatan.
    Gunakan kotak pencarian untuk mencari data tertentu.
  - Tab Status File menampilkan hasil tiap file beserta temuan dan catatannya.

Langkah 5: Simpan
  Klik Simpan CSV atau Simpan Excel. Setelah tersimpan, tombol Buka File muncul
  untuk membuka hasilnya. Nama file bawaan:
    - Penetapan         : rekening_belanja_dpa_penetapan
    - Parsial/Perubahan : rekening_belanja_dpa_parsial_perubahan
    - RAK               : anggaran_kas_ diikuti tahap dokumen

Tampilan gelap bisa diaktifkan dari sakelar Mode gelap di kiri bawah.


5. FORMAT HASIL
--------------------------------------------------------------------------------
Menu DPA:

  Kolom               Isi
  ------------------  --------------------------------------------------------
  kode_kegiatan       Kode dari baris Kegiatan
  nama_kegiatan       Nama dari baris Kegiatan. Teks HURUF BESAR diubah menjadi
                      format judul, misalnya Pelaksanaan Kebijakan Perekonomian
  kode_sub_kegiatan   Kode dari baris Sub Kegiatan
  nama_sub_kegiatan   Nama dari baris Sub Kegiatan
  kode_rekening       Kode rekening 6 segmen, misalnya 5.1.02.01.001.00024
  nama_rekening       Nama rekening
  pagu                Nominal rekening tanpa pemisah ribuan, misalnya 120000.
                      Pada DPPA dipakai nilai Setelah.
  sumber_dana         Isi baris Sumber Dana di bawah rekening
  keterangan          Selalu kosong

  - Satu rekening dengan dua sumber dana menjadi dua baris. Pagu tiap baris
    adalah bagian sumber dana tersebut.
  - Pada DPPA, rekening baru ikut hasil dengan nilai Setelah. Rekening atau
    sumber dana yang nilai Setelah-nya Rp0 tidak ikut hasil, dan rekening yang
    dilewati tercatat di tab Status File.
  - Hasil hanya berisi sub kegiatan yang PDF-nya diproses. Sub kegiatan tanpa
    PDF DPPA tidak otomatis diambil dari hasil penetapan.

Menu RAK:

  Kolom               Isi
  ------------------  --------------------------------------------------------
  kode_sub_kegiatan   Kode dari baris Sub Kegiatan
  kode_rekening       Kode rekening 6 segmen; baris induk dilewati
  nama_rekening       Nama rekening
  pagu                Kolom Anggaran Tahun Ini
  jan sampai des      Kolom Januari sampai Desember

  - Tahap dokumen dibaca dari judul file, lalu tampil di pesan selesai dan di
    tab Status File. Jangan mencampur tahap berbeda dalam satu proses.
  - Rekening dengan semua nilai 0 tidak ikut hasil dan tercatat di tab Status
    File.

File hasil:
  - File Excel memakai kolom yang sama, dengan nilai uang berupa angka.
  - File CSV memakai encoding UTF-8 dengan BOM dan pemisah titik koma (;).
    DPA Penetapan         : akhir baris CRLF, tanda kutip hanya bila perlu.
    DPA Parsial/Perubahan : akhir baris LF, kolom nama dan sumber_dana dikutip.
    RAK                   : akhir baris LF, kolom nama_rekening dikutip.


6. ARTI HASIL VALIDASI
--------------------------------------------------------------------------------
Kartu Validasi:
  Total cocok    Semua pemeriksaan lolos.
  N temuan       Ada hal yang perlu diperiksa di tab Status File.
  N file gagal   Ada file yang tidak bisa dibaca atau tidak sesuai menu.

Catatan berwarna abu-abu di tab Status File bukan masalah. Isinya penjelasan
perlakuan normal, misalnya rekening Rp0 yang tidak disertakan.

Pemeriksaan pada semua menu:
  Rekening muncul di dua file
      Bila ya: peringatan, baris ditandai.

Pemeriksaan pada menu DPA:
  Jumlah pagu sama dengan Jumlah Anggaran Sub Kegiatan
      Bila tidak cocok: error.
  Nilai rekening sama dengan jumlah per sumber dana
      Bila tidak cocok: error, baris ditandai.
  Nominal rekening bisa dibaca
      Bila tidak: error, baris ditandai.
  Sumber dana rekening ditemukan
      Bila tidak: peringatan, memakai Sumber Pendanaan sub kegiatan.
  Bentuk huruf dikenali dengan yakin
      Bila tidak: peringatan, baris ditandai.
  DPPA: Setelah dikurangi Sebelum sama dengan Bertambah/Berkurang
      Bila tidak cocok: error, baris ditandai.
  DPPA: jumlah nilai Sebelum sama dengan total Sebelum di dokumen
      Bila tidak cocok: error.

Pemeriksaan pada menu RAK:
  Anggaran sama dengan Total RAK dan jumlah 12 bulan
      Bila tidak cocok: error, baris ditandai.
  Jumlah tiap bulan sama dengan baris total PER BULAN di file
      Bila tidak cocok: error.
  Jumlah pagu sama dengan Nilai Anggaran
      Bila tidak cocok: error.
  Ada nilai yang bukan angka
      Bila ya: error, rekening tersebut dilewati.
  Tahap dokumen tercampur dalam satu proses
      Bila ya: peringatan.

Penting:
- Baris yang ditandai berwarna kuning di tab Hasil Ekstraksi dan TETAP IKUT
  TERSIMPAN. Periksa temuan sebelum memakai datanya.
- File yang gagal dibaca tidak ikut tersimpan.


7. BATASAN
--------------------------------------------------------------------------------
- PDF hasil scan (berupa gambar) belum didukung dan akan ditolak.
- PDF yang hurufnya berupa gambar vector dibaca dengan font Arial bawaan
  Windows. Bila kolom data memakai font lain, baris itu mendapat peringatan.
- Nama yang terpotong ke baris baru tepat setelah tanda - atau / yang menempel
  pada kata disambung tanpa spasi, misalnya Bidang- dan Keuangan menjadi
  Bidang-Keuangan. PDF tidak membedakannya dengan nama berspasi seperti
  Kantor- Kertas yang kebetulan terpotong di titik yang sama; pada kasus itu
  spasinya hilang. Periksa nama seperti ini di hasil Anda.
- Pengubahan HURUF BESAR mengenali singkatan dari daftar tetap, seperti BUMD,
  BLUD, dan UMKM. Singkatan di luar daftar berubah menjadi Abcd tanpa
  peringatan.
- Rekening dengan dua sumber dana baru diuji dengan data buatan.
- Excel RAK tahap Penetapan dan Parsial yang asli belum pernah diuji; pengujian
  dengan file asli baru memakai tahap Perubahan.


8. MASALAH YANG SERING TERJADI
--------------------------------------------------------------------------------
Windows protected your PC (SmartScreen) atau peringatan antivirus
    Exe belum ditandatangani secara digital. Pada SmartScreen, klik More info
    lalu Run anyway, bila file berasal dari sumber yang Anda percaya.

Dokumen ini DPPA; gunakan menu Extract DPA Parsial/Perubahan
Dokumen ini DPA Penetapan; gunakan menu Extract DPA Penetapan
    PDF dimasukkan ke menu yang salah. Buka menu yang disebutkan.

Gagal menyimpan, file sedang dibuka di aplikasi lain
    Tutup file tersebut di Excel, lalu simpan lagi.

Bukan file RAK Belanja yang dikenali
    File Excel tersebut bukan RAK Belanja dari SIPD, misalnya hasil simpanan
    aplikasi ini atau RAK Pendapatan.

Tahap dokumen berbeda dari file lain
    Satu proses berisi RAK dari tahap berbeda. Pisahkan per tahap.

File rusak atau bukan PDF
File rusak atau bukan Excel
    File tidak bisa dibuka. Unduh atau cetak ulang filenya.

Format file tidak didukung; simpan sebagai .xlsx
    File masih berformat lama. Buka di Excel, lalu simpan sebagai .xlsx.

PDF berupa gambar hasil scan
    Cetak ulang dokumen dari SIPD menjadi PDF.

Baris 'Sub Kegiatan' tidak ditemukan
    PDF tersebut bukan DPA atau DPPA Rincian Belanja SKPD.

Font tidak ditemukan
    Font Arial tidak ada di C:\Windows\Fonts. Pulihkan font bawaan Windows.

Jumlah rekening tidak sama dengan total dokumen
    Ada nominal yang perlu dicek. Bandingkan baris pada tab Hasil Ekstraksi
    dengan dokumen aslinya.


9. DISCLAIMER
--------------------------------------------------------------------------------
Hasil ekstraksi dibaca otomatis dari PDF dan dapat mengandung kesalahan. Periksa
hasilnya dengan dokumen asli sebelum digunakan.

Aplikasi ini disediakan apa adanya, tanpa jaminan apa pun. Pembuat tidak
bertanggung jawab atas kerugian yang timbul dari penggunaan aplikasi ini.

Aplikasi ini bukan bagian dari SIPD. Dokumen asli tetap menjadi acuan resmi.


10. LISENSI
--------------------------------------------------------------------------------
Copyright (c) 2026 adawarjo

SmartExtract adalah perangkat lunak bebas di bawah GNU Affero General Public
License versi 3 (AGPL-3.0-only). Anda boleh memakai, mengubah, dan menyebarkannya,
selama versi yang Anda sebarkan juga menyertakan kode sumbernya di bawah lisensi
yang sama. Ketentuan lengkapnya ada di LICENSE.txt.

Kode sumber: https://github.com/adawarjo/smartextract

Teks lisensi dan catatan komponen pihak ketiga juga bisa dibuka dari menu About.
