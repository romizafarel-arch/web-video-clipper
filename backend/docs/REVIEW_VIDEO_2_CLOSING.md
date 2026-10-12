# Review penutupan Video 2 dan kesiapan Video 3

Tanggal: 29 September 2026.

Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.

Baseline: `main`, `fb3aee9b156dabb8ec1b0b14913f189208507766`, ditambah patch lokal. Working tree masih memiliki perubahan produksi dan berkas tes/fixture/dokumentasi yang belum di-commit. Reviewer tidak mengubah kode produksi dan tidak menjalankan API.

## Keputusan

**Validasi empiris Video 2 dapat dicatat selesai dengan PASS pada pipeline/integritas media dan temuan editorial yang belum diperbaiki. Kesiapan eksekusi Video 3 masih memerlukan satu koreksi kecil pada propagasi cancellation/timeout diagnostik.**

Ini tidak membatalkan tiga hasil MP4, tidak membuka kembali Bagian A–C, dan tidak membutuhkan inferensi Video 2 baru. Persiapan dokumen, sumber, dan batas API Video 3 dapat dilanjutkan sementara koreksi tersebut dikerjakan.

## 1. Koreksi yang terverifikasi

- `end` segmen kini berasal dari `round(seg_end, 2)`; floor durasi 0,1 detik sudah dihapus. Probe 10,00–10,02 menghasilkan end 10,02.
- Interval nol dipertahankan tanpa perpanjangan, sesuai kontrak `end >= start`. Ini penerimaan skema timestamp, bukan klaim cue berdurasi nol dapat dibaca penonton.
- `_parse_offset` menolak bool sebelum tipe numerik. Probe True ditolak.
- Hash diagnostik membaca blok 65.536 byte; hash hasil cocok dengan SHA-256 langsung pada fixture beberapa blok. Pemakaian buffer hash tidak lagi sebanding dengan ukuran video sumber.
- Fixture `tests/fixtures/segment_86_sanitized.json` tersedia dan memiliki regresi mandiri. Tes payload lengkap tetap opsional bila artefak lokal tidak ada; regresi inti tidak lagi hanya bergantung pada output lokal.
- Runner sekarang menulis `validation_v2_summary_{job_id}.json`, selain pointer summary terbaru. Ini perbaikan untuk run mendatang, bukan bukti summary job terdahulu telah direkonstruksi.
- Reviewer mengulang seluruh suite: **101 tes, 39,596 detik, OK, tanpa skip** pada mesin ini. Perbedaan lama eksekusi dari laporan tidak menunjukkan kegagalan.
- Checksum cache Video 1, audio/source Video 2, tiga MP4, metadata dan summary cold run pertama cocok dengan catatan review sebelumnya. Media tidak di-decode ulang karena hash identik dengan media yang sudah lolos decode penuh pada review sebelumnya.

## 2. Satu temuan tersisa: V2-C01 [P2], exception kontrol tertelan

Lokasi utama:

`C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\shorts_generator\local\gemini_transcriber.py:457`

Loop hashing memanggil `job_ctx.check_cancellation_or_timeout()`, tetapi blok `except Exception: pass` menangkap `JobCancelledException` dan `JobTimeoutException`. Handler luar helper pada baris 497 juga menangkap seluruh Exception.

Probe menggunakan helper produksi yang diekstrak tanpa perubahan melalui AST, kelas exception asli proyek, fixture lokal 320 KB, dan context yang melempar exception pada checkpoint hashing:

| Sinyal | Exception diteruskan? | Diagnostik tetap ditulis? | source_sha256 |
| --- | --- | --- | --- |
| JobCancelledException | Tidak | Ya | null |
| JobTimeoutException | Tidak | Ya | null |

Probe tambahan menjalankan fungsi `transcribe_with_gemini` asli dengan seluruh Client/SDK transport diganti mock lokal. Sinyal stop diaktifkan setelah respons model, sehingga pertama kali diperiksa dalam hashing. Pada kedua kasus, fungsi tetap mengembalikan transkrip, bukan meneruskan exception. Seluruh operasi model/upload/delete pada probe adalah mock, tanpa jaringan.

Alur `transcribe_local` kemudian masih dapat menulis cache sebelum checkpoint pipeline berikutnya. Pipeline memang mempunyai checkpoint setelah transkripsi; **review ini tidak membuktikan worker akhirnya melaporkan completed setelah cancel**, dan tidak menyatakan demikian. Celah yang terbukti adalah sinyal kontrol ditelan, fungsi melanjutkan publikasi, dan penghentian ditunda sampai checkpoint tahap berikutnya.

Tes hashing baru hanya memeriksa kesamaan hash pada jalur sukses. Karena belum mencakup cancellation/timeout, 101 tes yang lulus belum mendeteksi celah ini.

### Koreksi minimal

1. Perlakukan `JobCancelledException` dan `JobTimeoutException` sebagai exception kontrol yang harus langsung diteruskan; jangan menelannya sebagai kegagalan hash/diagnostik biasa.
2. Periksa kedua handler helper: handler hashing dan handler luar diagnostik.
3. Periksa handler Path A pada baris 626: setelah helper meneruskan exception, jangan sampai `except Exception` mengubahnya menjadi fallback model multimodal. Cleanup File API dalam finally tetap dijalankan.
4. Tambahkan regresi cancel dan timeout selama hashing: exception keluar sampai caller, tidak ada fallback, tidak ada publikasi transkrip/cache setelah sinyal yang sudah teramati. Jalur worker dapat diuji dengan SDK mock; tidak memerlukan API riil.

Tidak diperlukan perubahan framework, perombakan lifecycle, pengulangan audit A–C, atau pemrosesan tiga video ulang.

## 3. Penutupan editorial: temuan telah diakui, hasil belum diperbaiki

Pemetaan terbaru lebih objektif:

- Klip 1 membutuhkan edit besar: pembuka wide shot gagal mempertahankan wajah dalam crop; durasi 64,8 detik melampaui target pengujian 15–60; akhir menggantung menurut transkrip.
- Klip 2 memiliki masalah crop pada transisi shot detik lokal ke-5. Label edit ringan dapat digunakan sebagai perkiraan bila koreksi singkat memang memungkinkan; belum ada waktu perbaikan terukur.
- Klip 3 memiliki sampel framing lebih baik, tetapi audio, lip-sync, akurasi caption, dan keutuhan narasi belum diverifikasi penuh. Ganti label ambigu “Siap Dipakai / Perlu Verifikasi Audio” menjadi **“Belum disahkan siap publikasi; menunggu verifikasi audio”**.

Laporan sudah mencabut klaim ASS/VTT identik 0 ms dan mengakui sync terhadap ucapan belum terukur. Itu benar. Pernyataan bahwa panjang stream sama membuktikan tidak ada A/V drift tetap perlu dibatasi: panjang stream tidak membuktikan sinkronisasi perceptual atau offset tetap.

Kalimat “inspeksi audiovisual independen” terlalu luas bila inspeksi aktual baru frame/metadata/transkrip dan audio manual dinyatakan belum dilakukan. Tulis metode yang benar-benar digunakan. Caption dan transkrip cukup untuk menandai indikasi akhir menggantung, tetapi tidak boleh disamakan dengan hasil mendengar seluruh audio.

Status penutupan berarti skenario validasi selesai dan temuan tercatat. Ini tidak berarti framing sudah diperbaiki atau ketiga video telah siap rilis. Tidak wajib menjalankan API ulang untuk memperbaiki atau menilai hasil editorial yang ada.

## 4. Catatan audit trail

- Kronologi tiga job dan sumber payload Segmen 86 kini telah dicatat. Replay pada payload job 61097 tetap membuktikan mekanisme baseline; penyebab spesifik payload cold run pertama tidak memiliki raw record yang identik.
- Metadata job 61097 menunjukkan **25,19 detik**, dari 12:51:37.16059 sampai 12:52:02.352872. Laporan menyebut 24,74 detik tanpa penjelasan dasar ukur yang berbeda. Koreksi atau beri label sumber pengukuran; ini koreksi dokumentasi, bukan kegagalan media.
- Bukti persetujuan terpisah untuk run tambahan 61097 belum tersedia dalam materi yang diperiksa. Jangan menyatakan kepatuhan jumlah run total sudah disahkan hanya karena counter tiap job memenuhi batas. Catat status izin sebagai belum terkonfirmasi bila tidak ada bukti.
- Jumlah request yang tidak memiliki summary per-job harus ditandai sebagai rekonstruksi berdasarkan artefak/log yang tersedia. Jangan menyatakan tabel kumulatif lebih presisi daripada buktinya.
- Delete File API sudah dilabeli attempted; status sukses cleanup remote tidak dibuktikan dengan counter tersebut. Token dan biaya tetap belum terukur.
- Sebelum eksekusi Video 3, simpan patch, tes dan fixture yang dibutuhkan ke commit selektif baru setelah regresi lulus. Jangan memasukkan .env, output media, cache, venv, atau profil QA. HEAD fb3aee9 sendiri belum memuat koreksi ini. Review tidak membuat commit.

## 5. Persiapan Video 3 yang proporsional

### Sumber dan jumlah chunk

Pilih sumber tetap **40–45 menit** jika tujuannya membuktikan tiga chunk tanpa memperbesar durasi uji. Probe fungsi `chunk_transcript` produksi dengan segmen sintetis tersebar sepanjang video mengonfirmasi:

| Durasi sumber | Chunk terbentuk | Request highlight nominal tanpa retry |
| --- | --- | --- |
| 35 menit | 2 | 3 |
| 40 menit | 3 | 4 |
| 45 menit | 3 | 4 |
| 58 menit | 3 | 4 |
| 60 menit | 4 | 5 |

Request highlight nominal adalah satu klasifikasi konten ditambah satu ranking per chunk. Jumlah aktual chunk bergantung pula pada segmen relevan yang tersedia. Sumber >58 menit dapat membentuk chunk keempat; rentang umum 40–60 menit tidak menjamin tepat tiga chunk.

**Jangan menyalin batas dua highlight Video 2 secara langsung.** Untuk tiga chunk, rencana nominal membutuhkan empat request highlight. Tetapkan batas yang disetujui pengguna, guard dispatch yang cocok, SDK retry nol, dan kebijakan atas respons invalid. Catatan ini merupakan rekomendasi rencana, bukan izin menjalankan request berbayar.

### Bukti dan profil

- Gunakan output/cache `output_val_v3` yang terisolasi sebelum import modul dan source lokal tetap. Pertahankan artefak Video 1/2.
- Simpan log dan summary per Job ID; simpan respons per chunk sebelum offset/deduplikasi dengan sanitasi kredensial.
- Periksa awal, boundary 1140–1260, chunk berikutnya, dan akhir aktual. Highlight >=600 detik tidak membuktikan chunk berikutnya.
- Catat waktu klasifikasi serta ranking setiap chunk, peak memory bila dapat diukur, status cancellation/timeout, dan waktu gabungan pemrosesan tiap klip. Jangan mengarang durasi tahap yang belum diinstrumentasi.
- Bila AI tidak memilih bagian akhir, gunakan uji editorial manual pada media yang ada dan pisahkan dari bukti seleksi otomatis. Tidak perlu memicu AI baru hanya untuk memenuhi lokasi kandidat.

### Latensi LLM dan timeout

Pada Video 2, ranking memakan 268,17 detik, 52,5% total; pemrosesan klip 211,08 detik, 41,3%. Untuk Video 3, ukur tiap chunk terlebih dahulu. Tiga ranking dengan durasi serupa berarti sekitar 804 detik hanya untuk ranking, **sekadar skenario kapasitas, bukan prediksi hasil Video 3**. Durasi transkripsi sumber panjang belum dapat disimpulkan dari uji 484 detik.

Evaluasi kecukupan timeout job 1800 detik terhadap rencana tersebut. Jangan mematikan timeout atau menaikkannya tanpa batas. Perubahan model, chunk size, concurrency, dan akselerasi render sebaiknya menjadi eksperimen performa terpisah setelah baseline video panjang tercatat, agar sebab perubahan waktu dapat dinilai.

## 6. Bukti reviewer

Direktori artefak:

`C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`

- `review_v2_closing_probes.py`: helper/fungsi produksi melalui AST, mock SDK lokal, dan probe jumlah chunk.
- `review_v2_closing_probes.json`: bukti exception tertelan, hash normal, offset pendek/nol, preservasi checksum, dan perencanaan chunk.
- `review_v2_closing_unittest.txt`: 101 tes, OK.

Tidak ada API berbayar dijalankan atau kode produksi diperbaiki oleh reviewer pada audit ini.
