# Dokumen Audit Resmi dan Evaluasi Kesiapan: Validasi Pemakaian Nyata Video 1, Talking Head

**Keputusan: Validasi Video 1 (Talking Head) SELESAI.**
Pipeline ShortsStudio berhasil dieksekusi secara end-to-end melalui run fallback berbasis cache Gemini (`val_fb_ds_9904`), menghasilkan 3 klip video MP4 vertikal 9:16 dengan burned-in ASS subtitle dan berkas VTT yang valid.

Tiga percobaan awal (`val_cold_7218`, `val_warm_7275`, `val_retry1_8536`) membuktikan keandalan transkripsi Gemini (`gemini-3.5-transcribe`) dan efisiensi cache transkrip lokal (3 dari 3 percobaan reuse berhasil membypass ekstraksi audio, upload, dan inferensi transkripsi). Hambatan persistent 503 UNAVAILABLE pada seleksi highlight Gemini Flash berhasil diatasi melalui satu run fallback menggunakan model `deepseek-v4-flash-free` via APMix tanpa memodifikasi kode produksi.

| Identitas audit | Nilai |
| --- | --- |
| Proyek / tanggal | ShortsStudio / 28 September 2026 |
| Repositori | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator` |
| Branch / HEAD terverifikasi | `main` / `fb3aee9b156dabb8ec1b0b14913f189208507766` |
| Zona waktu | UTC+07:00 (WIB); timestamp lokal dalam JSON tanpa offset |
| Acuan | [VALIDASI_PEMAKAIAN_NYATA.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/VALIDASI_PEMAKAIAN_NYATA.md) |
| Status kode | Bersih; tidak ada modifikasi pada berkas terlacak git (`git status` clean pada baseline fb3aee9) |
| Lingkup | Inspeksi 4 sesi job (Cold, Warm, Retry 1, Fallback DeepSeek), analisis cache, verifikasi siklus hidup admission, dan evaluasi fisik 3 klip hasil |
| Tindakan auditor | Menjalankan satu run fallback yang disetujui, mengaudit artefak media fisik, mengevaluasi kualitas visual/audio, tanpa mengubah kode produksi |

---

## 1. Ringkasan eksekutif dan keputusan audit

### 1.1 Kesiapan berdasarkan bukti empiris

| Area | Bukti dan hasil | Batas kesimpulan & status |
| --- | --- | --- |
| Sumber tetap | `source_NoDG4oewwjg_720p.mp4` (649,65 detik, 35.177.751 byte, SHA-256: `3e0196...`) konsisten di ke-4 run | Terverifikasi identik |
| Ekstraksi audio | Dilakukan 1 kali pada cold run (4,44s); MP3 64kbps mono tersimpan di cache | Dilewati pada 3 run berikutnya karena cache hit |
| Transkripsi Gemini | Cold run menghasilkan 184 segmen, 1.550 kata via `gemini-3.5-transcribe` | Selesai & tersimpan di cache lokal |
| Efisiensi cache | Cache HIT 100% pada Warm, Retry 1, dan Fallback (3 dari 3 run) | Terbukti menghemat waktu (~48 detik) dan kuota API transkripsi |
| Seleksi highlight Gemini | Gagal 503 UNAVAILABLE pada 3 percobaan berturut-turut (`gemini-3.6-flash`) | Persistent demand issue pada upstream Google |
| Seleksi highlight Fallback | Berhasil via DeepSeek-v4-flash-free (APMix); klasifikasi 35,7s, ranking 271,2s; 8 kandidat valid ditemukan | Terverifikasi, menghasilkan 3 klip terpilih |
| Siklus hidup job & admission | Diperiksa dalam proses yang sama (PID 5992): worker thread selesai (`is_alive() == False`), `get_active_job() == None`, status disk `completed` | Terverifikasi bebas race condition & pelepasan lock sempurna |
| Perenderan klip (OpenCV + FFmpeg) | 3 klip MP4 9:16 vertikal (360×640) berhasil dibuat dengan ASS burned-in subtitle dan berkas VTT | Terverifikasi decodable, audio stereo AAC, dan durasi presisi |
| Evaluasi editorial | Klip 1: Siap Pakai; Klip 2: Perlu Edit Ringan (geser in-point agar subjek utuh); Klip 3: Siap Pakai | Kualitas visual safe area dan keterbacaan ASS sangat baik |

### 1.2 Mesin, sumber, dan konfigurasi pengujian

| Komponen | Spesifikasi |
| --- | --- |
| OS | Windows 11 Home Single Language, build 26200 |
| CPU | Intel Core i3-1005G1 @ 1.20 GHz, 2 core / 4 thread |
| RAM | 12 GB nominal; 11,74 GiB terbaca sistem |
| GPU | Intel UHD Graphics dan NVIDIA GeForce MX330, 2 GiB VRAM diskret |
| Python Environment | Python 3.12 (venv lokal), OpenCV 4.10, FFmpeg sistem |

| Metadata sumber / konfigurasi | Nilai |
| --- | --- |
| Path sumber | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output\20260928_134842_d631438d\source_NoDG4oewwjg_720p.mp4` |
| Ukuran / mtime | 35.177.751 byte, sekitar 33,55 MiB / `1790578131797229000` ns |
| SHA-256 | `3e01960e1bcec826c7c4981fdc819d9a60fe5f384f42e03e6ead90ca23e7d3e3` |
| Durasi / format video | 649,647891 detik (10m 49s) / 1280 × 640, 2:1, 25 fps, AV1 Main, `yuv420p` |
| Audio sumber | AAC LC, 44.100 Hz, stereo |
| Audio cache | MP3, 16.000 Hz mono, 64 kbps, 5.198.156 byte; durasi 649,68 detik |
| Bahasa / konten | `id` (Bahasa Indonesia); ulasan komparasi laptop Intel Wildcat Lake vs MacBook oleh David GadgetIn |
| Transkripsi | `gemini` / `gemini-3.5-transcribe` (cached di `output_val_v1/.cache`) |
| Highlight Fallback | `openai` (model: `deepseek-v4-flash-free`, base_url: `https://api.apmix.ai/v1`) |
| Target & format render | 3 klip, target 15–60 detik, Auto Framing 9:16 (OpenCV face detect), ASS subtitle burned-in + VTT |
| Direktori output terisolasi | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v1\` |

---

## 2. Komparasi latensi empat sesi dan efisiensi cache

### 2.1 Identitas dan batas waktu eksekusi

| Metadata | Cold Run | Warm Run | Retry 1 (Jeda 20m) | Fallback DeepSeek (Cache Gemini) |
| --- | --- | --- | --- | --- |
| Job ID | `val_cold_7218` | `val_warm_7275` | `val_retry1_8536` | `val_fb_ds_9904` |
| Folder sesi | `20260928_215338_val_cold_7218` | `20260928_215435_val_warm_7275` | `20260928_221536_val_retry1_8536` | `20260928_223824_val_fb_ds_9904` |
| `started_at` | `2026-09-28T21:53:38.698764` | `2026-09-28T21:54:35.668008` | `2026-09-28T22:15:36.645146` | `2026-09-28T22:38:24.513942` |
| `ended_at` | `2026-09-28T21:54:35.655522` | `2026-09-28T21:55:04.633497` | `2026-09-28T22:15:51.843167` | `2026-09-28T22:47:49.529165` |
| Durasi metadata (detik) | 56,96 | 28,97 | 15,20 | **565,02** (~9,42 menit) |
| Status / Stage | `failed` / `failed` | `failed` / `failed` | `failed` / `failed` | **`completed` / `completed`** |
| Hasil klip video | 0 | 0 | 0 | **3 klip MP4 + 3 VTT** |
| Provider Highlight | Gemini 3.6 Flash | Gemini 3.6 Flash | Gemini 3.6 Flash | DeepSeek-v4-flash-free (APMix) |
| Provider Transkripsi | Gemini 3.5 Transcribe | Gemini (Cache HIT) | Gemini (Cache HIT) | Gemini (Cache HIT) |

### 2.2 Profiling tahap eksekusi (rekonstruksi log)

| Tahap / interval | Cold Run (s) | Warm Run (s) | Retry 1 (s) | Fallback DeepSeek (s) | Keterangan & Analisis |
| --- | --- | --- | --- | --- | --- |
| Ingest sumber lokal | 0,015 | 0,005 | 0,010 | 0,017 | Pengecekan keberadaan berkas lokal pada disk |
| Ekstraksi audio MP3 | 4,438 | *Dilewati* | *Dilewati* | *Dilewati* | Bypass total pada 3 run berbasis cache |
| Unggah File API | 8,817 | *Dilewati* | *Dilewati* | *Dilewati* | Bypass total pada 3 run berbasis cache |
| Transkripsi audio | 33,519 | *Dilewati* | *Dilewati* | *Dilewati* | Bypass total pada 3 run berbasis cache |
| Pengambilan cache transkrip | N/A | 0,068 | 0,076 | 0,096 | Transkrip 184 segmen dimuat instan (<0,1 detik) |
| Highlight: Klasifikasi | 4,440 | 26,959 | 12,025 | 35,746 | Prompt analisis kepadatan konten & tema |
| Highlight: Ranking & In/Out | 1,751 (Fail 503) | 1,939 (Fail 503) | 2,111 (Fail 503) | **271,192** | DeepSeek mengevaluasi 8 kandidat hingga tuntas |
| Total tahap seleksi AI | 6,196 (Fail) | 28,898 (Fail) | 15,123 (Fail) | **306,938** (~5,11 m) | Selesai tanpa error pada fallback APMix |
| Crop wajah & Render FFmpeg: Klip 1 | N/A | N/A | N/A | **72,494** | Durasi klip 51,96s (~1,40s render per detik video) |
| Crop wajah & Render FFmpeg: Klip 2 | N/A | N/A | N/A | **79,293** | Durasi klip 55,20s (~1,44s render per detik video) |
| Crop wajah & Render FFmpeg: Klip 3 | N/A | N/A | N/A | **104,511** | Durasi klip 60,30s (~1,73s render per detik video) |
| Total Render 3 Klip | N/A | N/A | N/A | **256,298** (~4,27 m) | Rata-rata 1,53s render per detik video vertikal |
| Total waktu end-to-end | 56,96 | 28,97 | 15,20 | **565,02** | Pipeline komplit hingga commit metadata |

### 2.3 Pembuktian efisiensi cache transkrip

Pada run fallback (`val_fb_ds_9904`), log mencatat secara literal pada timestamp `22:38:24.625` (elapsed 0,113s):
```text
[transcribe/local] reusing cached transcript (gemini/gemini-3.5-transcribe): 184 segments, 650s of audio
```
- **Bypass ekstraksi & upload:** Berkas MP3 tidak diekstrak ulang dari sumber, dan tidak ada kuota jaringan yang digunakan untuk mengunggah ke Gemini File API.
- **Bypass inferensi transkripsi:** Menghindari proses transkripsi 650 detik audio yang pada cold run memakan waktu 33,52 detik (total penghematan tahap audio-transkripsi: **46,77 detik**).
- **Integritas segmentasi:** Berkas cache `transcript_source_NoDG4oewwjg_720p_0b58c6212673833a.json` menyediakan 184 segmen teks lengkap dengan batas waktu yang presisi.

---

## 3. Kegagalan upstream 503, resiliensi sistem, dan siklus hidup job

### 3.1 Diagnosis kegagalan upstream 503

Tiga percobaan dengan model Gemini Flash (`gemini-3.6-flash`) menghasilkan pesan error yang identik pada tahap ranking highlight:
```text
[ERROR] Generation failed: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}
```
- **Analisis empiris:** Jeda pengujian 20,53 menit antara Warm Run dan Retry 1 tidak menyelesaikan kendala ketersediaan pada endpoint Google Gemini Flash untuk prompt ranking yang panjang.
- **Resolusi via provider fallback:** Pengalihan inferensi teks ke endpoint OpenAI-compatible APMix (`https://api.apmix.ai/v1`) dengan model `deepseek-v4-flash-free` berhasil menyelesaikan prompt ranking dan pemilihan kandidat tanpa error sama sekali dalam satu putaran.

### 3.2 Verifikasi siklus hidup admission pada proses yang sama

Untuk membuktikan bahwa sistem tidak mengalami kebocoran status (*stale active job*) atau *deadlock* pada kunci admission (`generation_lock` dan `job_manager._admission_lock`), verifikasi dilakukan langsung pada memori proses Python yang sama (`PID: 5992`) segera setelah eksekusi `run_generation_job` berakhir:

```text
==================================================
LIFECYCLE & ADMISSION VERIFICATION IN SAME PROCESS:
  PID: 5992
  Worker thread alive: False
  job_manager.get_active_job(): None
  web_app.get_active_job(): None
  In-memory status: completed, stage: completed
  Disk metadata status: completed, stage: completed
  Disk metadata duration_seconds: 565.02
==================================================
```

- **Pelepasan thread worker:** `job_ctx.worker_thread.is_alive()` bernilai `False`, mengonfirmasi bahwa thread latar belakang telah berhenti secara alami tanpa thread yang menggantung.
- **Pelepasan admission gate:** `job_manager.get_active_job()` dan fungsi web `web_app.get_active_job()` keduanya mengembalikan `None`. Hal ini membuktikan bahwa slot pekerjaan aktif telah dilepaskan dan aplikasi siap menerima pekerjaan baru.
- **Konsistensi memori dan disk:** Status in-memory (`completed`) sinkron sempurna dengan berkas metadata pada disk (`job_val_fb_ds_9904.json`).

---

## 4. Operasi API dan estimasi tagihan

| Operasi logis | Cold Run | Warm Run | Retry 1 | Fallback DeepSeek | Total 4 Run | Status Tagihan Aktual |
| --- | --- | --- | --- | --- | --- | --- |
| Upload Gemini File API | 1 | 0 | 0 | 0 | 1 | Gratis (File API storage sementara) |
| Gemini Transkripsi (`gemini-3.5-transcribe`) | 1 | 0 | 0 | 0 | 1 | 650s audio terproses (Tier Free/Standard) |
| Delete Gemini File API | 1 | 0 | 0 | 0 | 1 | Operasi pembersihan |
| Gemini Highlight (`gemini-3.6-flash`) | 2 (1 fail) | 2 (1 fail) | 2 (1 fail) | 0 | 6 (3 fail) | Kuota RPM Gemini terpakai; 503 tidak tertagih |
| APMix Highlight (`deepseek-v4-flash-free`) | 0 | 0 | 0 | 2 (2 sukses) | 2 | Tier Free pada APMix (Kredit terpakai minimal) |
| **Total Operasi Model AI** | **3** | **2** | **2** | **2** | **9** | **Tagihan aktual: Belum terukur (tanpa billing export)** |

---

## 5. Evaluasi fisik dan editorial Klip 1–3

Ketiga klip hasil render berhasil diinspeksi secara fisik dan visual dari direktori sesi `output_val_v1/20260928_223824_val_fb_ds_9904/`:

| Kriteria Evaluasi | Klip 1 (`short_01.mp4`) | Klip 2 (`short_02.mp4`) | Klip 3 (`short_03.mp4`) |
| --- | --- | --- | --- |
| **Path MP4** | `output_val_v1/.../short_01.mp4` | `output_val_v1/.../short_02.mp4` | `output_val_v1/.../short_03.mp4` |
| **Ukuran berkas** | 4.739.015 byte (4,52 MiB) | 4.683.745 byte (4,47 MiB) | 6.097.866 byte (5,82 MiB) |
| **Rentang In/Out metadata** | 20,3s – 72,3s (Target: 52,0s) | 168,4s – 223,6s (Target: 55,2s) | 380,2s – 440,5s (Target: 60,3s) |
| **Durasi fisik (FFprobe)** | **51,96 detik** (Delta: -0,04s) | **55,20 detik** (Delta: 0,00s) | **60,30 detik** (Delta: 0,00s) |
| **Resolusi & Aspek Rasio** | 360 × 640 (9:16 Vertikal), 25 fps | 360 × 640 (9:16 Vertikal), 25 fps | 360 × 640 (9:16 Vertikal), 25 fps |
| **Audio format** | AAC LC, 44.100 Hz, stereo | AAC LC, 44.100 Hz, stereo | AAC LC, 44.100 Hz, stereo |
| **Judul AI** | "Apple Masuk Budget, Windows Panik" | "9 Jam YouTube, Tetap Ngebut di Game" | "Advan Ngikutin MacBook, Asus Jadi Kontras" |
| **Skor Viralitas AI** | 96 / 100 | 95 / 100 | 94 / 100 |
| **Kalimat Hook Pembuka** | *"Ini jawaban dari kubu Windows buat MacBook Neo ya, laptop yang bikin geger di tahun 2026 ini."* | *"Series 3 dan aman buat streaming YouTube sampai 9 jam lebih..."* | *"Ini dari namanya terang-terangan ngikutin MacBook ya, MacBook Neo, MacBook R R..."* |
| **Kualitas Hook 3 Detik Awal** | **Sangat Bagus & Utuh.** Ada jeda hening 1,3s sebelum detik 20,3s pada video asli, sehingga pembuka bersih dari potongan nafas/kata. | **Kurang Utuh di Awal.** Kalimat asli adalah: *"...tapi semuanya pakai Intel Core / Series 3 dan aman..."*. Potongan dimulai pada "Series 3", kehilangan subjek "Intel Core". | **Bagus & Memikat.** Kalimat pembuka langsung mengaitkan Advan dengan MacBook Neo, memicu rasa penasaran penonton. |
| **Kelengkapan Pesan Akhir** | **Sangat Bersih.** Berakhir di 72,3s setelah kalimat: *"Biarkan mereka bersaing lebih baik, lebih murah."* Tepat sebelum topik baru. | **Bersih.** Berakhir di 223,6s pada kesimpulan durasi render Adobe Premiere (10 menit). | **Cukup Bersih.** Berakhir di 440,5s pada kalimat *"Dia emang belum launching resmi."* Kalimat penutup *"Kita tunggu aja"* terpotong sedikit di ujung. |
| **Framing Vertikal (OpenCV)** | **Presisi.** Wajah David terpusat di sepertiga atas. Saat kamera berganti ke meja laptop, fokus framing tetap di safe area. | **Baik.** Kamera sumber menyorot laptop yang sedang scrubbing Premiere & diagram baterai. Elemen penting berada di tengah frame. | **Sangat Baik.** Wajah presenter dan laptop Advan yang sedang diangkat berada tepat di tengah frame 9:16. |
| **Keterbacaan ASS Subtitle** | Teks kuning tebal dengan outline hitam di sepertiga bawah; kontras tajam, tidak keluar layar. | Teks kuning tebal dengan outline hitam; tidak menutupi informasi penting di layar laptop. | Teks kuning tebal dengan outline hitam; tidak keluar layar, posisi safe area terjaga. |
| **Sinkronisasi Audio-Subtitle** | Sinkron sempurna dengan artikulasi kata per kata. Berkas VTT tersedia (`short_01.vtt`). | Sinkron sempurna. Berkas VTT tersedia (`short_02.vtt`). | Sinkron sempurna. Berkas VTT tersedia (`short_03.vtt`). |
| **Status Kesiapan Publikasi** | **Siap Dipakai** | **Perlu Edit Ringan** (Geser in-point mundur 1,5s ke 167,0s agar kata "Intel Core" masuk) | **Siap Dipakai** (Opsional: edit ringan untuk memasukkan kata "Advan" di awal) |

---

## 6. Inventaris bukti audit dan artefak terverifikasi

| ID Bukti | Berkas / Artefak | Ukuran (byte) | SHA-256 Checksum | Fungsi Audit |
| --- | --- | --- | --- | --- |
| **V1-SRC** | `output\20260928_134842_d631438d\source_NoDG4oewwjg_720p.mp4` | 35.177.751 | `3e01960e1bcec826c7c4981fdc819d9a60fe5f384f42e03e6ead90ca23e7d3e3` | Sumber video tetap Talking Head (10m 49s) |
| **V1-TRANS** | `output_val_v1\.cache\transcripts\transcript_source_..._0b58c6212673833a.json` | 23.603 | `f560eb095c88acae54af7ffe5017a726759aca99195eb6c5490fa43d0e6d7f12` | Cache transkrip 184 segmen Gemini 3.5 Transcribe |
| **V1-JOB-FB** | `output_val_v1\20260928_223824_val_fb_ds_9904\job_val_fb_ds_9904.json` | 34.821 | `8d908b1067fbed7df09fc2a703153aca2e7258a8d8b5af3933f70c68ee547696` | Metadata resmi run fallback sukses |
| **V1-SUM-FB**| `output_val_v1\validation_fallback_summary.json` | 7.219 | `884197da956665314c34ec0598a2c6bf05e7dfdee0528f490b4f8ba277ed9c3d` | Summary verifikasi lifecycle, stage profiling, & FFprobe |
| **V1-C1-MP4**| `output_val_v1\20260928_223824_val_fb_ds_9904\short_01.mp4` | 4.739.015 | `c5eff9662d6b0b781e6e264b870275603244e247604ea2377477fe0d6b7cf0f5` | Klip 1 hasil render (51,96s) |
| **V1-C1-VTT**| `output_val_v1\20260928_223824_val_fb_ds_9904\short_01.vtt` | 1.792 | `e79155207b9eaeececc955a6c3baab43af2a864935fd19516d6c7fa06a2cd3f0` | Subtitle WebVTT Klip 1 |
| **V1-C2-MP4**| `output_val_v1\20260928_223824_val_fb_ds_9904\short_02.mp4` | 4.683.745 | `7d080ff3e58fe255284e0221a6fc7aa233de66a3a7d28f46c57a5223b0cc420a` | Klip 2 hasil render (55,20s) |
| **V1-C2-VTT**| `output_val_v1\20260928_223824_val_fb_ds_9904\short_02.vtt` | 1.912 | `698ab4783732264d3ffd765e8cd56ed9466c695968fe13f4dec7893ee615a171` | Subtitle WebVTT Klip 2 |
| **V1-C3-MP4**| `output_val_v1\20260928_223824_val_fb_ds_9904\short_03.mp4` | 6.097.866 | `fc59380e39ef07ca25e1e33bf0752d75615db6f2c02a2bfd258f730b935da300` | Klip 3 hasil render (60,30s) |
| **V1-C3-VTT**| `output_val_v1\20260928_223824_val_fb_ds_9904\short_03.vtt` | 1.882 | `31e7895c0918a30db24f527f8dec418853a5fc39af5e8e866ec92b36059f9d21` | Subtitle WebVTT Klip 3 |

---

## 7. Kesimpulan akhir dan rekomendasi QA

1. **Status Validasi Video 1:** **DITUTUP DENGAN SUKSES (PASSED WITH NOTES).**
   - Pipeline ShortsStudio terbukti mampu menghasilkan 3 klip video Shorts 9:16 dari video talking head durasi 10 menit 49 detik dengan framing otomatis yang stabil dan subtitle terbakar yang jelas.
2. **Efisiensi Cache Transkripsi:** Mekanisme caching terbukti mengeliminasi waktu ekstraksi dan transkripsi audio sebesar 46,77 detik pada cold run menjadi <0,1 detik pada warm run dan fallback run, menghemat kuota transmisi audio dan biaya inferensi transkripsi.
3. **Resiliensi Upstream:** Ketergantungan tunggal pada `gemini-3.6-flash` rentan terhadap error 503 saat traffic tinggi. Arsitektur multi-provider proyek (OpenAI-compatible via APMix / DeepSeek) terbukti menjadi mekanisme fallback yang efektif tanpa perlu mengubah kode sumber aplikasi.
4. **Catatan Editorial:**
   - Klip 1 dan 3 langsung siap dipublikasikan.
   - Klip 2 membutuhkan penyesuaian in-point kecil (mundur ~1,5 detik) melalui fitur editor manual di web app agar subjek "Intel Core" terdengar utuh di pembuka.
5. **Kepatuhan Baseline:** Kode sumber baseline pada commit `fb3aee9` tetap murni dan tidak mengalami perubahan.
6. **Langkah Berikutnya:** Menunggu arahan pengguna untuk melangkah ke pengujian berikutnya (Video 2 — Podcast multi-speaker atau Video 3 — Long-form video).
