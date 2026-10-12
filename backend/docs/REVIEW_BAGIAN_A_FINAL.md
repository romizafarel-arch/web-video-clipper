# Pengesahan review Bagian A, ShortsStudio

Tanggal: 28 September 2026.
Checkout: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`, branch `main`, perubahan lokal belum di-commit.

**Keputusan: Bagian A diterima dan dapat ditutup untuk lingkup aplikasi lokal satu pengguna, Flask satu proses, berdasarkan kriteria penutup yang sudah disepakati. Tidak ada penghalang tambahan yang ditemukan dalam review penutup ini. Bagian B dapat dimulai sesuai roadmap.**

Ini bukan pengesahan keamanan/keandalan seluruh proyek atau jaminan terhadap semua variasi media. Scope review adalah ketepatan editor, referensi sumber, isolasi edit, perlindungan artefak pada kegagalan yang tertangkap, verifikasi durasi hasil, dan akses tombol editor mobile.

## Verifikasi independen

### Suite proyek

**41/41 tes lulus dalam 3,482 detik; 0 kegagalan, 0 error, 0 skip.**

Suite menggunakan venv checkout utama. Output diarahkan ke direktori sementara sebelum aplikasi diimpor dan Python dijalankan dengan `-B`. Source proyek tidak diedit oleh reviewer.

Pada percobaan awal, 40 tes lulus dan tes integrasi FFmpeg tidak dapat dimulai melalui PATH sesi review. FFmpeg yang sudah terpasang ditemukan di paket WinGet `yt-dlp.FFmpeg`. PATH ditambahkan hanya untuk proses pengujian; tidak ada instalasi atau perubahan PATH permanen. Setelah itu seluruh suite lulus, termasuk render FFmpeg nyata dari 2 sampai 6 detik.

Jumlah berdasarkan tes yang ditemukan: 15 backend, 24 editorial, 2 highlights. Total 41 yang dilaporkan agen benar; pembagian 12/27/2 dalam laporan agen tidak sesuai discovery, tetapi tidak memengaruhi hasil tes.

### Koreksi A-05

Kode aktual `web_app.py:167-174` memakai:

```python
frame_period = 1.0 / fps if fps > 0 else 0.04
allowed_tolerance = min(0.5, max(0.25, frame_period * 3.0))
```

Toleransi kini dibatasi 0,25 sampai 0,5 detik, tidak membesar mengikuti panjang klip. Itu memenuhi koreksi yang diminta pada putaran sebelumnya.

Probe reviewer memakai MP4 riil OpenCV dan verifier aktual tanpa mock:

| Hasil fisik | Selection | Verdict |
|---|---|---|
| 2 detik | 8 detik | Ditolak |
| 7 detik | 8 detik | Ditolak |
| 26 detik | 30 detik | Ditolak |
| 30 detik | 30 detik | Diterima |

Endpoint yang disodori renderer simulasi dengan MP4 fisik 26 detik untuk selection 30 detik mengembalikan HTTP 500 sebelum promotion. Probe reviewer membandingkan bytes MP4, VTT, dan JSON sebelum/sesudah penolakan: ketiganya identik. Tes suite juga membuktikan kasus endpoint 7/8 menjaga MP4/VTT dan metadata lama. Regresi durasi riil 7,967/8 dan 29,933/30 lulus sehingga pembulatan normal tetap dapat diterima.

`test_real_ffmpeg_normal_render_passes_verification` benar-benar menjalankan FFmpeg, `crop_clip_local`, dan verifier aktual. Render normal 4 detik lulus dengan toleransi baru.

### Delapan kondisi kegagalan sebelumnya

Semua probe reviewer dijalankan ulang dan cocok dengan hasil yang diharapkan:

- Error metadata commit dengan restore sukses memulihkan MP4/VTT lama.
- Error commit disertai restore gagal mempertahankan backup MP4/VTT untuk pemulihan manual.
- Gagal unlink VTT memicu HTTP 500 dan rollback; tidak lagi melaporkan sukses palsu.
- Tidak ada MP4 lama lalu commit gagal: MP4 baru dibersihkan.
- Tidak ada VTT lama lalu commit gagal: VTT baru dibersihkan.
- Dua render editorial klip berbeda yang tumpang tindih mempertahankan metadata kedua klip.
- Hasil staging 2 detik untuk selection 8 detik ditolak.
- Rentang 99,8–100,4 pada sumber 100 detik ditolak karena durasi efektif terlalu pendek.

### JavaScript editor aktual

Node VM dengan stub DOM/player menjalankan source JavaScript aplikasi, bukan salinan rumus di Python. Hasil:

- Origin 605 + player 12,4 menghasilkan 617,4 pada Set In berulang, input In manual, dan fallback sumber gagal.
- Save lalu reopen tanpa refresh mempertahankan In/Out dan judul terbaru.
- Handler Tonton memakai revisi terbaru.
- Save tanpa subtitle menghapus track; save dengan subtitle baru membuat/memperbarui track dengan revision URL.
- Download mengikuti revision URL yang sama.

### Browser mobile independen

Reviewer membuka aplikasi aktual melalui Codex In-app Browser dengan output fixture terisolasi, tanpa menyentuh hasil pengguna. Viewport diuji pada **320×568** dan **390×844**.

Editor dibuka dari riwayat melalui UI, form di-scroll ke bawah, lalu bounding box dibandingkan dengan modal dan viewport. Hit test pada pusat kedua tombol mengembalikan tombol yang benar. Tombol Batal diklik dan modal menutup; fokus kembali ke Edit.

| Viewport | Batal di modal/viewport | Simpan di modal/viewport | Hit test keduanya | Batal berfungsi |
|---|---|---|---|---|
| 320×568 | Lulus | Lulus | Lulus | Lulus |
| 390×844 | Lulus | Lulus | Lulus | Lulus |

Pengujian ini menutup kesenjangan assertion browser agen yang sebelumnya hanya memeriksa batas horizontal dan keterjangkauan tombol Simpan. Kedua tombol memang dapat dijangkau setelah scroll; tidak harus tampak sekaligus sebelum pengguna menggulir.

Screenshot reviewer:

- `review-editor-320px-final.png`
- `review-editor-390px-final.png`

Fixtur browser reviewer menggunakan codec MP4V dari OpenCV yang tidak diputar oleh browser uji tersebut. Oleh karena itu sesi ini memverifikasi layout, scroll, hit testing, dan pembatalan modal; tidak diklaim sebagai pengujian pemutaran/re-render video di browser. Validasi render nyata dilakukan oleh tes FFmpeg dan verifikasi media di atas. Script Chrome CDP dan screenshot agen juga diperiksa, tetapi seluruh runner Chrome CDP agen tidak dijalankan ulang oleh reviewer.

Server sementara sudah dihentikan, fixture sementara dibersihkan, tab uji ditutup, dan override viewport direset. Kode, konfigurasi, atau video proyek tidak diubah.

## Status A-01 sampai A-08

| ID | Status dalam scope review |
|---|---|
| A-01 | Diterima: origin dan selection terpisah, zero drift pada kondisi yang diuji |
| A-02 | Diterima: per-clip render lock dan per-session commit lock untuk satu proses |
| A-03 | Diterima: rollback pada error yang tertangkap dan backup dipertahankan jika restore gagal |
| A-04 | Diterima: probe sumber wajib, normalisasi EOF konsisten, minimum durasi efektif divalidasi |
| A-05 | Diterima: toleransi terbatas, awal/akhir video diperiksa, hasil pendek ditolak, hasil normal lulus |
| A-06 | Diterima: VTT stale tidak dipublikasikan pada jalur normal, failure unlink membatalkan transaksi |
| A-07 | Diterima: identitas indeks/file dan registry diuji dengan validasi backend |
| A-08 | Diterima: state editor, pemutar, track, download, dan history mengikuti revisi terakhir |

## Batas jaminan yang tetap berlaku

- MP4, VTT, dan JSON masih dipromosikan sebagai beberapa operasi file. Ini bukan transaksi multi-file atomik atau jaminan ACID terhadap mati listrik/proses mati.
- Jika rollback gagal, backup memungkinkan pemulihan manual; file final dapat masih tidak konsisten dengan metadata sampai pemulihan dilakukan. Aplikasi memberikan error, bukan sukses, pada kondisi itu.
- Locks bersifat process-local. Koordinasi dengan cancel/delete session atau writer pipeline menjadi lingkup lifecycle Bagian B.
- Verifikasi awal/akhir dan durasi bukan pemindaian setiap frame/audio dan belum mencakup seluruh ragam footage pengguna.

Batas tersebut sudah sesuai ruang lingkup yang disepakati dan bukan alasan membuka kembali Bagian A. Pertahankan seluruh regresi serta koreksi ini ketika mengerjakan Bagian B.
