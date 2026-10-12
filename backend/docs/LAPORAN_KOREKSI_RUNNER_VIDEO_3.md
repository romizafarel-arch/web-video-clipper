# Laporan Pelaksanaan Koreksi Runner Validasi Video 3 — ShortsStudio

Tanggal Pelaksanaan: 29 September 2026, zona waktu UTC+07:00.  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.  
Baseline Git: Branch `main`, commit `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`.  
Dokumen Acuan: [REVIEW_KOREKSI_RUNNER_VIDEO_3.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_KOREKSI_RUNNER_VIDEO_3.md) & [REVIEW_PERSIAPAN_VIDEO_3.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_PERSIAPAN_VIDEO_3.md).

---

## 1. Ringkasan Eksekutif

Koreksi penutup pada runner validasi Video 3 telah diselesaikan sepenuhnya untuk menuntaskan dua residu tersisa dari **V3-01** (cleanup upload saat sinyal stop dan finalisasi aman summary JSON), menyelaraskan fungsi runner dengan suite pengujian (**V3-02**), serta meluruskan batas-batas klaim teknis sesuai tinjauan independen.

Pekerjaan tetap dibatasi secara ketat pada harness dan dokumentasi persiapan (`scratch/run_validation_v3.py`, `scratch/test_guards_v3_offline.py`, `docs/RENCANA_VALIDASI_VIDEO_3_PANJANG.md`, dan dokumen ini). **Tidak ada kode produksi di `shorts_generator/` atau `web_app.py` yang diubah**, tidak ada pemanggilan API berbayar, dan tidak ada media yang diunduh.

Status suite pengujian:
- **Suite Guard Offline Video 3 (`scratch/test_guards_v3_offline.py`)**: **21/21 tes lulus** dalam 9,821 detik (OK).
- **Suite Unittest Kode Produksi**: 108/108 tes lulus pada baseline `bbd2c4de` (kode produksi tidak tersentuh perubahan).
- **Preservasi Artefak Terdahulu**: 10/10 berkas referensi Video 1 dan Video 2 terbukti identik secara SHA-256.

---

## 2. Rincian Penutupan Residu V3-01 & Perapian V3-02

### 2.1 Penutupan Residu V3-01.a: Cleanup Upload Bersamaan dengan Cancel/Timeout

| Aspek | Masalah Terdahulu | Implementasi Koreksi Baru (`run_validation_v3.py`) | Pembuktian Offline |
| :--- | :--- | :--- | :---: |
| **Mekanisme Cleanup pada Batas Upload** | Jika `Files.upload` SDK mengembalikan berkas bernama namun post-check mengangkat exception kontrol, berkas staging tertinggal tanpa pembersihan karena caller belum memasuki blok `try/finally`. | Wrapper `_tracked_files_upload` menangkap `(JobCancelledException, JobTimeoutException)` setelah `_orig_files_upload` selesai; jika `res.name` ada, wrapper mengupayakan `self.delete(name=res.name)` via wrapper cleanup terikat 15 detik sebelum melempar kembali exception asli. | Terbukti (`test_16`, `test_17`, `test_18`) |
| **Preservasi Exception Kontrol** | Kegagalan koneksi saat delete tidak boleh menutupi error pembatalan. | Handler penghapusan diisolasi dalam `try...except Exception: pass`. Jika delete gagal, counter `delete_failed` dicatat, dan exception kontrol asli (`JobCancelledException` / `JobTimeoutException`) tetap diteruskan tanpa modifikasi. | Terbukti (`test_19`) |
| **Pencegahan Double-Delete** | Jalur sukses tidak boleh menghapus berkas saat upload. | Pada alur normal tanpa sinyal pembatalan, objek File dikembalikan utuh ke caller. Penghapusan baru dilakukan satu kali di blok `finally` caller transkripsi. | Terbukti (`test_20`) |
| **Batas Klaim Teknis** | Klaim jaminan staging bersih 100% tidak realistis jika jaringan putus sebelum server mengembalikan ID berkas. | Ditegaskan bahwa cleanup adalah **upaya terikat dengan hasil tercatat**, yang hanya dapat dijalankan jika File ID sudah diterima dari server SDK. | Terdokumentasi |

### 2.2 Penutupan Residu V3-01.b: Penantian Worker & Serialisasi Aman Summary

| Aspek | Masalah Terdahulu | Implementasi Koreksi Baru (`run_validation_v3.py`) | Pembuktian Offline |
| :--- | :--- | :--- | :---: |
| **Penantian Worker Thread** | Batas luar `thread.join(timeout=1860.0)` dapat kembali saat worker masih berjalan. | Dihapus batas join buatan: diganti menjadi `thread.join()`, mengandalkan timeout request per-panggilan SDK dan checkpoint kooperatif internal 1.800 detik. | Terbukti di harness |
| **Serialisasi Summary JSON** | Pengambilan langsung `in_memory_active_ctx` menghasilkan objek `JobContext` yang tidak serializable (`TypeError: Object of type JobContext is not JSON serializable`), menggagalkan penulisan summary. | Nilai `in_memory_active_ctx` disanitasi menjadi string ID (`job_ctx.job_id`) atau `None`; `in_memory_active_webapp` disanitasi menjadi string ID. `json.dumps` dijamin sukses. | Terbukti (`test_21`) |
| **Perlindungan Status Final** | Jika worker masih hidup (`worker_thread_alive = True`), artefak tidak boleh dianggap final. | Runner memeriksa `worker_thread_alive`; jika aktif, seluruh klip diberi `verified_complete = False` dengan catatan eksplisit "verifikasi final ditangguhkan", mencegah promosi prematur. | Terbukti (`test_21`) |

### 2.3 Penyelarasan V3-02 & Penataan Fungsi Runner

- **Ekstraksi Helper Kanonikal**: Logika pemetaan metadata diekstrak menjadi fungsi top-level `build_shorts_lookup(result_shorts)` pada `scratch/run_validation_v3.py`.
- **Pengujian Fungsi Riil**: Pengujian `test_13_partial_results_mapping_v3_02` pada `scratch/test_guards_v3_offline.py` kini memanggil langsung fungsi `rv3.build_shorts_lookup(result_shorts)`, membuktikan fungsi runner secara langsung bukan rekonstruksi internal tes.

### 2.4 Pelurusan Dua Klaim Dokumentasi

1. **Batas Cleanup**: Cleanup File API dicatat sebagai **upaya dengan hasil terekam**, bukan jaminan mutlak jika jaringan terputus sebelum File ID diperoleh.
2. **Cakupan Fail-Fast**: Fail-fast yang terbukti mencakup penolakan perulangan aplikasi ranking (`MAX_HIGHLIGHT_API_ATTEMPTS = 1`), larangan fallback transkripsi multimodal, dan pembatasan kuota inferensi (Policy B/B). Fungsi `detect_content_type` di kode produksi tetap mempertahankan penanganan bawaan (fallback ke klasifikasi kategori `other/medium` jika terjadi error parsing).

---

## 3. Matriks Lengkap Pengujian Offline (`test_guards_v3_offline.py`)

Eksekusi: `.\.venv\Scripts\python.exe scratch/test_guards_v3_offline.py -v`  
Hasil: **21 tes lulus dari 21 tes (100% OK)**, durasi total 9,821 detik.

| ID Tes | Fokus Pengujian | Status | Durasi |
| :--- | :--- | :---: | :---: |
| `test_01` | Highlight cap guard memblokir request ke-5 sebelum jaringan | Lulus | <0,01s |
| `test_02` | Transcribe guard memblokir model fallback multimodal & cap ke-2 | Lulus | <0,01s |
| `test_03` | Ranking JSON invalid/kosong langsung berhenti (*fail-fast*) tanpa retry aplikasi | Lulus | <0,01s |
| `test_04` | Sinyal cancel dan deadline job meneruskan exception kontrol | Lulus | <0,01s |
| `test_05` | Isolasi binding direktori output `LOCAL_OUTPUT_DIR = output_val_v3` | Lulus | <0,01s |
| `test_06` | Simulasi chunking 40m (2400s) menghasilkan 3 chunk & 4 request LLM nominal | Lulus | 0,05s |
| `test_07` | Simulasi chunking 45m (2700s) menghasilkan maksimal 3 chunk tanpa chunk ke-4 | Lulus | 0,02s |
| `test_08` | Preservasi SHA-256 berkas Video 1 dan Video 2 identik | Lulus | 0,11s |
| `test_09` | **V3-01**: Pembatalan selama request aktif OpenAI dan Gemini melempar `JobCancelledException` | Lulus | 0,01s |
| `test_10` | **V3-01**: Batas waktu habis selama request aktif OpenAI dan Gemini melempar `JobTimeoutException` | Lulus | 0,01s |
| `test_11` | **V3-01**: Parameter timeout diteruskan ke SDK: OpenAI detik (float), Gemini ms (int) | Lulus | <0,01s |
| `test_12` | **V3-01**: Tidak ada dispatch lanjutan setelah sinyal stop (cancel/timeout) | Lulus | <0,01s |
| `test_13` | **V3-02**: Pemetaan metadata hasil parsial langsung melalui `build_shorts_lookup` | Lulus | <0,01s |
| `test_14` | **V3-01/Profiling**: Counter polling bertambah sesuai jumlah panggilan `Files.get` | Lulus | <0,01s |
| `test_15` | **V3-01**: Operasi delete File API tetap diupayakan dengan batas waktu saat job dibatalkan | Lulus | <0,01s |
| `test_16` | **V3-01.a**: Cancel selama upload membersihkan File ID yang diketahui dan melempar `JobCancelledException` | Lulus | <0,01s |
| `test_17` | **V3-01.a**: Caller transkripsi nyata `transcribe_with_gemini` menangkap cancel upload, cleanup 1x, generate 0 | Lulus | <0,01s |
| `test_18` | **V3-01.a**: Deadline habis saat upload mengupayakan cleanup dan melempar `JobTimeoutException` | Lulus | <0,01s |
| `test_19` | **V3-01.a**: Kegagalan delete saat stop mencatat `delete_failed` dan mempertahankan exception kontrol asli | Lulus | <0,01s |
| `test_20` | **V3-01.a**: Upload normal tidak memicu cleanup prematur; delete dipanggil tepat satu kali oleh caller | Lulus | <0,01s |
| `test_21` | **V3-01.b**: Serialisasi aman summary JSON tanpa `TypeError` saat worker masih hidup & penangguhan verifikasi | Lulus | <0,01s |

---

## 4. Bukti Preservasi Artefak Terdahulu (10 Berkas Referensi)

Pemeriksaan SHA-256 membuktikan integritas mutlak pada 10 artefak referensi Video 1 dan Video 2:

| No | Berkas Artefak | Ukuran (Bytes) | Hash SHA-256 Terverifikasi | Status |
| :---: | :--- | :---: | :--- | :---: |
| 1 | `output_val_v1/20260928_223824_val_fb_ds_9904/short_01.mp4` | 4.739.015 | `c5eff9662d6b0b781e6e264b870275603244e247604ea2377477fe0d6b7cf0f5` | Identik |
| 2 | `output_val_v1/20260928_223824_val_fb_ds_9904/short_02.mp4` | 4.683.745 | `7d080ff3e58fe255284e0221a6fc7aa233de66a3a7d28f46c57a5223b0cc420a` | Identik |
| 3 | `output_val_v1/20260928_223824_val_fb_ds_9904/short_03.mp4` | 6.097.866 | `fc59380e39ef07ca25e1e33bf0752d75615db6f2c02a2bfd258f730b935da300` | Identik |
| 4 | `output_val_v1/.cache/audio/audio_source_NoDG4oewwjg_720p_a5e65e36c711911b.mp3` | 5.198.156 | `6bf4ba6ea6b5cb3fd046fce2748424685551a968afe1a076bc918ffe174a4faf` | Identik |
| 5 | `output_val_v1/.cache/transcripts/transcript_source_NoDG4oewwjg_720p_0b58c6212673833a.json` | 23.603 | `f560eb095c88acae54af7ffe5017a726759aca99195eb6c5490fa43d0e6d7f12` | Identik |
| 6 | `output_val_v2/source_podcast_v2_clip.mp4` | 51.273.714 | `43ac0f46579386afd6da70db811486eafa61619b0a665e3ef6e8e34eb739a1f2` | Identik |
| 7 | `output_val_v2/.cache/audio/audio_source_podcast_v2_clip_cfed8f56508e4c9e.mp3` | 3.873.068 | `271389ddbd8f4b6dafeb4b5ddc398cf42e6a2698f48135c6b792fedc6a257108` | Identik |
| 8 | `output_val_v2/20260929_130009_val_v2_pod_verify_61609/short_01.mp4` | 6.828.918 | `e3f0553bcd974147e85833dc91a2a6a88219d086c3853d60b044e4f2e05c22d5` | Identik |
| 9 | `output_val_v2/20260929_130009_val_v2_pod_verify_61609/short_02.mp4` | 5.704.805 | `e10f81619b9c809288f994159e088d2a0ea165d2c871b63977b40a817ed2f68f` | Identik |
| 10 | `output_val_v2/20260929_130009_val_v2_pod_verify_61609/short_03.mp4` | 7.118.832 | `c630c1dcf0e24c728cb281b25069dc0818df38b4dbc52125610ece953a7c5f47` | Identik |

---

## 5. Keputusan Masukan Pengguna yang Dibutuhkan Sebelum Cold Run

Sesuai protokol batas eksekusi, harness pengujian Video 3 telah siap secara teknis. Pelaksanaan cold run nyata berbayar kini hanya menunggu konfirmasi 4 parameter berikut dari pengguna:

1. **Sumber Media Video 3**:
   - Jalur berkas lokal (disarankan: berkas lokal MP4 berdurasi 40–45 menit dengan ucapan stabil melampaui detik 2280), atau URL YouTube yang disepakati untuk diunduh.
2. **Bahasa Transkripsi Audio**:
   - Default rencana: Bahasa Indonesia (`id`).
3. **Penyedia & Model Inferensi**:
   - Model Transkripsi: Google Gemini `gemini-3.5-transcribe` via File API.
   - Model Ranking Highlights: APMix `deepseek-v4-flash-free`.
4. **Persetujuan Kuota Maksimal API**:
   - Transkripsi: Tepat 1 inferensi Gemini Audio.
   - Highlight: Maksimal 4 inferensi APMix (1 klasifikasi densitas + 3 pemeringkatan per-chunk).
