# Closing review Bagian B — ShortsStudio

Tanggal: 28 September 2026.
Checkout: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`, branch `main`, perubahan lokal belum di-commit.

## Keputusan

**B-02, B-03, dan B-05 dapat ditutup. B-04 masih memiliki satu koreksi sebelum sign-off Bagian B.** B-01/B-06/B-07 dan status penutupan Bagian A tetap dipertahankan. Review ini tidak menambahkan fitur atau memperluas audit ke Bagian C.

## Verifikasi yang sudah lulus

- Suite lengkap terbaru: **62/62 lulus**, 5,373 detik, **0 failure, 0 error, 0 skip**, tidak menggantung. Seluruh 41 baseline Bagian A termasuk render FFmpeg nyata tetap lulus.
- Probe import Gemini: sukses, signature helper membawa `media_path` dan `job_ctx`; kode helper meneruskan konteks ke shared FFmpeg runner.
- Fault persistensi awal: status failed, alasan PermissionError terlihat, worker berhenti, tidak ada unhandled exception, pipeline tidak dimulai, request berikutnya diterima HTTP 200.
- Dua edit untuk klip yang sama: edit pertama 200, delete saat edit kedua aktif **409**, edit kedua 200, sesi tetap utuh.
- File korup kecil saat pembatalan klip pertama: status canceled, success 0, shorts kosong, dan status disk canceled.
- QA lifecycle Chrome tujuh skenario sudah diverifikasi pada review sebelumnya. Tidak dijalankan ulang pada closing review ini; penilaian bukti browser tetap dibatasi pada UI dengan state job simulasi, bukan generasi AI nyata. Skenario browser tersebut tidak memeriksa kesesuaian durasi media pada jalur retensi yang dibahas di bawah.

Probe lama memakai indeks klip pertama untuk pelaporan; ketika shorts kosong, daftar field memang harus menjadi []. Probe juga diperbaiki pada artefak review agar request kedua tidak memulai pipeline sesudah mock keluar. Ini perbaikan harness penguji, bukan perubahan kode aplikasi.

## B-04 — P2: retensi menerima video valid tetapi terlalu pendek

Lokasi:
- [web_app.py:423](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:423)
- [web_app.py:458](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:458)
- [web_app.py:469](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:469)

Helper `_collect_and_verify_completed_shorts` memanggil `verify_rendered_video(p)` tanpa `expected_duration`, baik pada kandidat maupun fallback scan disk. Pemeriksaan ini membuktikan file ada, cukup besar, dan dapat didekode; belum membuktikan durasinya sama dengan selection atau bahwa pipeline sudah mencatat render sebagai selesai.

Fallback disk masih memasukkan file kanonikal yang tidak terdapat di `completed_shorts`. Karena itu, penolakan file 23-byte sudah benar, tetapi MP4 pendek dengan container/header valid tetap bisa diterima. Ini merupakan bagian dari syarat lama: retensi hanya klip yang benar-benar selesai, dengan verifikasi media/durasi sesuai rentang.

### Bukti dengan MP4 FFmpeg nyata

Fixture mempunyai video sumber 12 detik dan selection 0–8 detik. File output yang tertinggal dibuat berdurasi 2 detik, memiliki container MP4 valid, dan dapat didekode. Pipeline fixture memicu cancellation sebelum mencatat penyelesaian klip.

Hasil worker sebenarnya:

```text
physical_duration: 2.0
expected_duration: 8.0
completion_records: 0
status: partial
success: 1
retained_selection: 0.0–8.0
disk_status: partial
```

Sebagai pembanding, verifier yang sama dengan `expected_duration=8.0` menolak media tersebut:

```text
RuntimeError: Durasi fisik video hasil render (2.00s) tidak sesuai
dengan durasi rentang yang diminta (8.00s, toleransi ±0.25s).
```

Pengujian ini memakai media FFmpeg nyata dan worker/collector asli, dengan alur interruption disimulasikan. Ini bukan klaim bahwa proses FFmpeg pada setiap cancellation di Windows selalu menghasilkan MP4 yang masih dapat didekode. Yang terbukti adalah kontrak collector saat menemukan media semacam itu.

## Koreksi minimum untuk penutupan

1. Utamakan daftar `completed_shorts` beserta metadata lengkap sebagai sumber klip yang telah selesai. Karena manifest tersebut sudah ada, pilihan paling sederhana adalah menghapus fallback penerimaan file dari glob mentah yang tidak memiliki bukti penyelesaian.
2. Pada klip yang dipertahankan, hitung `expected_duration = end_time - start_time` dari metadata terpercaya dan teruskan ke `verify_rendered_video`. Gunakan toleransi yang sudah disahkan di Bagian A; tidak perlu formula baru.
3. Jika fallback recovery disk tetap dipertahankan, wajib ada metadata terpercaya untuk identitas/rentang dan verifikasi durasi. Jangan mengisi waktu default lalu memperlakukan file tanpa bukti penyelesaian sebagai sukses.

Tes penutup yang diperlukan:
- MP4 valid 2 detik untuk selection 8 detik ditolak dalam jalur retensi cancel dan timeout.
- File tanpa bukti penyelesaian tidak otomatis menjadi klip sukses.
- Klip selesai dengan durasi cocok tetap partial setelah stop pada klip berikutnya, membawa identitas, timeline, metadata editorial, serta referensi sumber/transkrip yang benar.
- File korup/intermediate tetap ditolak; seluruh 62 tes regresi yang ada tetap lulus.

Setelah koreksi dan pengujian tersebut lulus, tidak diperlukan perubahan tambahan pada B-01/B-02/B-03/B-05/B-06/B-07 untuk closing review yang sama. Jangan mulai Bagian C sebelum satu residu ini ditutup.

## Artefak dan integritas

Probe: `review_b_closing_duration_probe.py`, tersedia di folder laporan ini. Semua source/media fixture berada di direktori sementara. Kode aplikasi, konfigurasi, working tree, dan media hasil pengguna tidak diubah oleh review. Tidak ada panggilan AI berbayar.
