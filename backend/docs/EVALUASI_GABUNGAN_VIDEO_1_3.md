# Dokumen Evaluasi Gabungan Hasil Validasi Pemakaian Nyata (Video 1–3) — ShortsStudio

**Status Dokumen:** Selesai & Final  
**Tanggal Evaluasi:** 30 September 2026 (WIB, UTC+07:00)  
**Repositori:** `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
**Baseline Kode Terverifikasi:** `main` (commit `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e` dengan patch transkripsi lokal)  
**Dokumen Acuan Utama:**  
1. [VALIDASI_PEMAKAIAN_NYATA.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/VALIDASI_PEMAKAIAN_NYATA.md)  
2. [LAPORAN_VALIDASI_VIDEO_1_TALKING_HEAD.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/LAPORAN_VALIDASI_VIDEO_1_TALKING_HEAD.md)  
3. [LAPORAN_VALIDASI_VIDEO_2_PODCAST.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/LAPORAN_VALIDASI_VIDEO_2_PODCAST.md)  
4. [LAPORAN_VALIDASI_VIDEO_3_PANJANG.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/LAPORAN_VALIDASI_VIDEO_3_PANJANG.md)  
5. [LAPORAN_REPLAY_VIDEO_3_API_RESMI.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/LAPORAN_REPLAY_VIDEO_3_API_RESMI.md)  
6. [LAPORAN_EVALUASI_VALIDASI_VIDEO_3_DAN_KESIAPAN_PUBLIKASI.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/LAPORAN_EVALUASI_VALIDASI_VIDEO_3_DAN_KESIAPAN_PUBLIKASI.md)

---

## 1. Ringkasan Hasil per Kategori Video

Evaluasi ini merangkum data empiris dari tiga kategori video nyata yang telah diuji pada siklus validasi ShortsStudio. Sesuai prinsip audit, evaluasi ini **secara tegas memisahkan keberhasilan teknis pipeline** (apakah kode berjalan, menghasilkan berkas, mematuhi kontrak data, dan lolos uji decode) **dari kualitas editorial yang benar-benar dinilai** (apakah klip nyaman ditonton, pesannya utuh, framing wajah tepat, dan subtitle sinkron).

### 1.1 Video 1: Talking Head (Monolog / Edukasi 1 Orang)
- **Karakteristik Media Sumber:**
  - Sumber: Video ulasan laptop David GadgetIn (`source_NoDG4oewwjg_720p.mp4`).
  - Durasi: 649,65 detik (10 menit 49 detik).
  - Format: 1280×640 (aspek rasio 2:1), 25 fps, AV1 Main, AAC audio stereo.
- **Keberhasilan Teknis Pipeline: LULUS (PASS)**
  - Ekstraksi audio menghasilkan MP3 mono 16 kHz 64 kbps (5,20 MB) dalam 4,44 detik.
  - Transkripsi STT via `gemini-3.5-transcribe` berhasil memproses 650 detik audio menjadi 184 segmen (1.550 kata) dalam 33,52 detik.
  - Mekanisme cache lokal terbukti 100% efektif pada 3 pengulangan (Warm Run, Retry 1, Fallback Run), menghemat ~48 detik per putaran dengan mem-bypass ekstraksi dan pengunggahan audio ke Gemini File API.
  - Manajemen siklus hidup pekerjaan (*job lifecycle*) dan admission gate terbukti bebas *race condition* dan pelepasan slot aktif berjalan bersih pada proses yang sama (`get_active_job() == None`).
  - Menghasilkan 3 berkas klip MP4 vertikal 9:16 (360×640) dengan subtitle ASS terbakar (*burned-in*) dan berkas sidecar WebVTT yang seluruhnya lolos uji decode penuh FFmpeg (`-xerror`, exit code 0).
  - *Catatan Kendala Upstream:* Model highlight utama `gemini-3.6-flash` mengalami error persistent HTTP 503 UNAVAILABLE pada 3 percobaan berturut-turut, namun pipeline berhasil diselesaikan via provider fallback OpenAI-compatible APMix (`deepseek-v4-flash-free`) tanpa mengubah kode produksi.
- **Kualitas Editorial yang Benar-benar Dinilai:**
  - *Klip 1 (51,96s):* **Siap Dipakai.** Pembuka hook utuh dan padat (*"Ini jawaban dari kubu Windows..."*), kalimat penutup selesai sebelum topik baru, wajah presenter berada stabil di safe area sepertiga atas.
  - *Klip 2 (55,20s):* **Perlu Edit Ringan / Besar.** Hook pembuka terpotong di awal (*"Series 3 dan aman..."*), kehilangan subjek utama (*"Intel Core"*). Secara visual, crop vertikal memotong diagram baterai dan teks benchmark laptop di layar sumber.
  - *Klip 3 (60,30s):* **Siap Dipakai (dengan catatan).** Hook menarik, namun durasi sedikit melebihi sasaran 60 detik (melebihi 0,30s), dan teks nama produk/poster di sisi samping terpotong oleh cropping 9:16.
  - *Batasan Penilaian:* Penilaian dilakukan berbasis inspeksi sampel frame statis dan pemeriksaan batas segmen transkrip; pemutaran audiovisual manusia secara kontinu belum menyeluruh.

---

### 1.2 Video 2: Podcast Dua Orang (Dialog / Percakapan Interaktif)
- **Karakteristik Media Sumber:**
  - Sumber: Cuplikan resmi Podcast Naik Clas (Soleh Solihun & Once Mekel, `source_podcast_v2_clip.mp4`).
  - Durasi: 484,00 detik (8 menit 4 detik).
  - Format: 1280×720, 25 fps, H.264 High, AAC stereo.
- **Keberhasilan Teknis Pipeline: LULUS DENGAN PATCH TEKNIS (PASS AFTER PATCH)**
  - *Kegagalan Awal (Cold Run 1):* Crash pada validasi kontrak semantik transkrip (`end < start` pada Segmen 86) akibat model STT Google mengeluarkan urutan kata mundur (*backward start jump*) pada percakapan bertumpuk (*backchannel / multi-speaker overlap*).
  - *Koreksi & Penguatan Arsitektur:* Diterapkan perbaikan bedah pada `shorts_generator/local/gemini_transcriber.py` dan `shorts_generator/local/transcriber.py` yang mencakup penghapusan durasi minimum buatan, penanganan kata berdurasi nol (`start == end`), pembacaan hash streaming 64 KB, serta penolakan tipe boolean.
  - *Ketahanan Sinyal Kontrol:* Penanganan exception `JobCancelledException` dan `JobTimeoutException` diperbaiki agar diteruskan langsung tanpa memicu fallback model atau penulisan cache korup.
  - *Suite Regresi:* 23 unit test baru ditambahkan (`tests/test_v2_transcript_regression.py`); seluruh 108 pengujian repositori lulus 100%.
  - *Run Verifikasi Sukses:* Job `val_v2_pod_verify_61609` (511,08 detik wall-clock) berhasil menghasilkan 3 klip MP4 9:16 (404×720) dan 3 berkas WebVTT yang lolos decode penuh FFmpeg (`-xerror`, exit code 0). Seluruh aset cache Video 1 terlindungi 100%.
- **Kualitas Editorial yang Benar-benar Dinilai:**
  - *Klip 1 (64,80s):* **Perlu Edit Besar.** Durasi fisik melebihi batas 60 detik. Pada detik 0,5 dan 5,0 (wide shot dua pembicara), crop otomatis memilih tengah meja kosong dan menyingkirkan kedua pembicara dari layar. Kalimat penutup menggantung pada detik 482,4s (*"ROYALTY KEPADA LMKN ATAS..."*).
  - *Klip 2 (48,08s):* **Perlu Edit Ringan.** Alur dialog dari setup hingga komedi (*punchline*) tersampaikan utuh. Namun pada detik ke-5 saat terjadi transisi shot, wajah pembicara terpotong di tepi kanan bingkai vertikal.
  - *Klip 3 (58,60s):* **Belum Disahkan Siap Publikasi (Menunggu Verifikasi Audio).** Narasi analogi pertemanan utuh dan framing wajah stabil di tengah frame, namun memerlukan verifikasi audio langsung sebelum publikasi.
  - *Temuan Subtitle:* Terbukti terdapat diskrepansi antara pembentukan takarir ASS (`target_chunk_size = 4` kata) dan WebVTT (`target_chunk_size = 5` kata), sehingga jumlah dan durasi cue berbeda (Klip 1: 42 cue ASS vs 37 cue VTT). Klaim sinkronisasi offset 0 ms dicabut; kesesuaian sinkronisasi perseptual $\pm 100$ ms berstatus **belum terukur secara perceptual**.

---

### 1.3 Video 3: Konten Berdurasi Panjang (Long-Form >30 Menit)
- **Karakteristik Media Sumber:**
  - Sumber: Video podcast edukasi psikologi Bicarakan ID (`source_long_v3.mp4`).
  - Durasi: 2.630,66 detik (43 menit 50,66 detik).
  - Format: 1280×720 @ 29.97 fps, H.264 Main, AAC stereo 44.100 Hz.
- **Keberhasilan Teknis Pipeline: LULUS PADA CONTROLLED REPLAY API RESMI (PASS)**
  - *Kegagalan Cold Run Awal:* Terhenti pada kata ke-1228 (`hyper`, start 516,3s > end 514,6s) dan ditemukannya 28 anomali kata terbalik dari respons `gemini-3.5-transcribe` (termasuk kata 2520 dengan start halusinasi 12.010,1s). Guard Policy B/B berhasil memblokir fallback liar dan menghapus berkas remote File API seketika.
  - *Controlled Replay API Resmi:* Transkrip 5.851 kata dibersihkan melalui modul sanitasi heuristik (*bounded recovery* pada 3 kata `hyper-arousal` dan penandaan 5 rentang tak terpercaya sepanjang 34,1 detik / 1,296% durasi media).
  - *Eksekusi API Resmi:* Menggunakan model `gemini-3.5-flash-lite` via endpoint Google Generative Language resmi. Seluruh 4 panggilan inferensi highlight (1 klasifikasi densitas + 3 pemrosesan chunk 20 menit) tuntas hanya dalam **9,47 detik** komputasi LLM.
  - *Integritas Render Fisik:* Menghasilkan 3 berkas klip MP4 vertikal 9:16 (404×720) dengan ASS burned-in subtitle dan berkas VTT. Ketiga klip lolos uji FFmpeg null decode (`exit code 0`, 0 frame rusak). Seluruh 68 berkas terproteksi (V1, V2, `.env`, master video, fixture) terjaga 100% utuh.
- **Kualitas Editorial yang Benar-benar Dinilai:**
  - *Status Umum:* Karena dieksekusi pada lingkungan headless/CLI tanpa monitor grafis dan output audio, seluruh klip diberi status resmi: **Belum dinilai secara audiovisual**.
  - *Klip 1 (19,486s):* **Kandidat Kuat.** Analogi luka diperban tersampaikan utuh dari premis hingga kesimpulan. Cue takarir berakhir di 18,0s dengan buffer jeda 1,48 detik sebelum potongan berakhir. Memerlukan checklist verifikasi manusia untuk framing 404×720 dan kejelasan teks ASS kuning.
  - *Klip 2 (37,471s):* **Tertunda / Perlu Tinjauan Editorial (Hold).** Terdeteksi celah ketiadaan cue takarir sepanjang **~9,3 detik** (detik 09,200–18,500), serta kata filler (*"ITU"*) dan interupsi lawan bicara (*"Semua apa?"*) menjelang akhir. Memerlukan verifikasi apakah celah 9,3 detik adalah hening canggung yang merusak retensi penonton.
  - *Klip 3 (30,800s):* **Tertunda / Perlu Pemangkasan Awal (Hold).** Memiliki 5 detik pengantar yang menggantung di awal (*"Dan juga biasanya ditandai dengan ada yang namanya Andre..."*), sedangkan hook utama baru dimulai pada detik ke-5 (*"Jadi itu respon di mana..."*). Memerlukan trimming awal manual agar klip langsung menyengat di detik pertama.

---

### 1.4 Matriks Rekapitulasi Komparatif Video 1–3

| Parameter Evaluasi | Video 1: Talking Head | Video 2: Podcast 2 Orang | Video 3: Video Panjang (>30 Mnt) |
| :--- | :--- | :--- | :--- |
| **Durasi Sumber** | 649,65 s (10m 49s) | 484,00 s (8m 04s) | 2.630,66 s (43m 50s) |
| **Resolusi Sumber & Format** | 1280×640 (2:1), AV1 | 1280×720 (16:9), H.264 | 1280×720 (16:9), H.264 |
| **Provider Transkripsi** | Gemini 3.5 Transcribe | Gemini 3.5 Transcribe | Gemini 3.5 Transcribe (Replay Fixture) |
| **Provider Highlight Sukses** | APMix (`deepseek-v4-flash-free`) | APMix (`deepseek-v4-flash-free`) | Google Gemini (`gemini-3.5-flash-lite`) |
| **Durasi Komputasi LLM** | 306,94 s (5,11 m) | 271,72 s (4,53 m) | **9,47 s** (4 inferensi tuntas) |
| **Durasi Fase Render Pasca-HL**| 256,30 s (4,27 m) | 211,08 s (3,52 m) | 234,20 s (3,90 m) |
| **Total Waktu Wall-Clock Run** | 565,02 s (~9,4 m) | 511,08 s (~8,5 m) | 243,67 s (~4,0 m) |
| **Jumlah Klip MP4 9:16 Dihasilkan**| 3 klip (360×640) | 3 klip (404×720) | 3 klip (404×720) |
| **Decode FFmpeg (`-xerror`)** | 3 dari 3 lolos (Exit 0) | 3 dari 3 lolos (Exit 0) | 3 dari 3 lolos (Exit 0) |
| **Efektivitas Cache Transkrip**| Hemat ~48 s (100% Hit) | Hemat ~25 s (Audio Reuse) | Transkrip Fixture Replay |
| **Status Teknis Pipeline** | **LULUS (PASS)** | **LULUS (PASS via Patch)** | **LULUS (PASS via Replay Resmi)** |
| **Status Kesiapan Editorial** | 2 Siap, 1 Edit Ringan | 2 Perlu Edit, 1 Hold Audio | 1 Kandidat Kuat, 2 Hold Editorial |
| **Biaya Tagihan Finansial** | Belum terukur | Belum terukur | Belum terukur (tanpa billing export) |

---

## 2. Masalah yang Berulang dan Dampaknya bagi Pengguna

Berdasarkan fakta empiris dari empat run eksekusi yang menghasilkan media dan tiga run kegagalan yang terdokumentasi, masalah dikelompokkan ke dalam tiga kategori:

### 2.1 Bug Teknis & Kerapuhan Arsitektur

1. **Kerapuhan Parsing dan Validasi Timestamp STT (Upstream AI Timestamp Jitter/Inversion):**
   - *Bukti & Angka:*
     - Video 2: Model mengembalikan kata dengan timestamp mundur pada dialog bertumpuk (Kata 674 `start: 329.8s` diikuti Kata 675 `325.8s` dan Kata 676 `325.9s–326.0s`), menghasilkan segmen korup `329.8s–326.0s` (`end < start`) yang menggagalkan run pertama.
     - Video 3: Model menghasilkan 28 kata dengan `end_offset < start_offset` (misal kata 1228 `hyper` start 516,3s > end 514,6s) dan lonjakan halusinasi hingga detik ke-12.010 pada video 2.630 detik, memicu `ValueError` kaku di `gemini_transcriber.py:365`.
   - *Dampak bagi Pengguna:* Seluruh proses transkripsi puluhan menit dan kuota API terbuang percuma hanya karena 1 kata mengalami glitch upstream. Tanpa guard, sistem mencoba fallback ke LLM multimodal yang sangat mahal; dengan guard kaku, sistem crash seketika (*fail-fast*).
   - *Status Mitigasi:* Di Video 2 dipatch secara bedah di tingkat segmenter adapter; di Video 3 dimitigasi via script sanitizer terpisah. **Belum terintegrasi sebagai lapisan pelindung runtime bawaan pada kode produksi.**

2. **Instabilitas dan Kegagalan Kuota Endpoint LLM Upstream (503 Unavailable & 429 TPM):**
   - *Bukti & Angka:*
     - Video 1: `gemini-3.6-flash` gagal 3 kali berturut-turut dengan status HTTP 503 UNAVAILABLE (`This model is currently experiencing high demand`) meskipun diberi jeda 20,5 menit.
     - Video 3 (Percobaan Replay Terdahulu): OpenAI API resmi gagal HTTP 429 pada t=2,62s (`insufficient_quota` / saldo $0); Groq API resmi gagal HTTP 429 pada model `openai/gpt-oss-120b` karena payload transkrip chunk (~8.800 token) melampaui batas 8.000 TPM Free Tier; APMix Proxy putus dengan HTTP 503 pada t=302,25 detik pemanggilan Chunk 2.
   - *Dampak bagi Pengguna:* Pekerjaan berhenti di tengah jalan setelah audio selesai ditranskripsi, menyebabkan ketidakpastian operasional dan pemborosan waktu tunggu.

3. **Diskrepansi Struktur Pembentukan Takarir Terbakar (ASS) vs Takarir Terpisah (WebVTT):**
   - *Bukti & Angka:* Kode pembentukan subtitle pada `shorts_generator/clipper.py` menggunakan konstanta pengelompokan kata yang berbeda: ASS memakai `target_chunk_size = 4` kata, sedangkan WebVTT memakai `target_chunk_size = 5` kata.
     - Akibatnya pada Klip 1 Video 2: ASS menghasilkan 42 cue sementara WebVTT menghasilkan 37 cue. Rentang 0–4,70s dibagi oleh ASS menjadi 3 bagian (0–1,57s, 1,57–3,13s, 3,13–4,70s), tetapi WebVTT membaginya menjadi 2 bagian (0–2,35s, 2,35–4,70s).
   - *Dampak bagi Pengguna:* Teks yang terbakar pada video MP4 tidak selaras secara batas cue dengan berkas `.vtt` yang dipakai untuk closed-caption di platform web. Pengguna yang mengoreksi berkas VTT akan mendapati tampilan teks video tidak cocok dengan berkas eksternal.

---

### 2.2 Kualitas Hasil (Editorial & Audiovisual)

1. **Auto-Crop Framing Naif pada Shot Multi-Speaker dan B-Roll:**
   - *Bukti & Angka:* Algoritme saat ini mengandalkan OpenCV Haar Cascade berbasis deteksi kotak wajah terbesar (`max(faces)`).
     - Video 1: Pada segmen B-roll laptop/grafik pengujian (Klip 2 detik 0,5/2,5s dan Klip 3 detik 30,15s), crop vertikal memotong informasi penting di tepi layar (diagram daya tahan baterai, angka benchmark, nama merek Advan, dan harga produk hilang).
     - Video 2: Pada wide shot dua orang (Klip 1 detik 0,5s dan 5,0s), crop memilih titik tengah meja kosong sehingga kedua pembicara berada di luar layar; pada Klip 2 detik 5,0s, transisi shot memotong separuh wajah subjek di batas kanan 9:16.
   - *Dampak bagi Pengguna:* Klip yang dihasilkan tidak siap publikasi secara estetika dan memerlukan penataan ulang komposisi (*re-framing*) manual di software pengedit video eksternal.

2. **Ketidaktepatan Penentuan Titik In/Out (Kalimat Menggantung & Pembuka Canggung):**
   - *Bukti & Angka:*
     - Video 1 (Klip 2): In-point tepat pada batas segmen transkrip 168,4s memotong kalimat pembuka (*"Series 3 dan aman..."*), kehilangan kata subjek *"Intel Core"* yang berada di akhir segmen sebelumnya.
     - Video 2 (Klip 1): Seleksi berdurasi 64,80s (melebihi pagu 60s) dan berhenti di detik 482,4s dengan cue *"ROYALTY KEPADA LMKN ATAS"*, memotong frasa penutup (*"lagu-lagu yang dipakai di event itu"*).
     - Video 3 (Klip 2 & 3): Klip 2 memiliki celah takarir sepanjang ~9,3 detik di tengah klip; Klip 3 memiliki pengantar menggantung 5 detik pertama sebelum hook utama muncul di detik 00:05.
   - *Dampak bagi Pengguna:* Penonton Shorts yang membutuhkan keterlibatan instan (*hook*) dalam 3 detik pertama disuguhi potongan kalimat canggung, sehingga retensi penonton berisiko anjlok drastis.

3. **Ketahanan Subtitle terhadap Alih Bahasa (Code-Switching) dan Batasan Pengukuran Perseptual:**
   - *Bukti & Angka:*
     - Istilah serapan bahasa Inggris pada video Indonesia (seperti *"hyper-arousal"*, *"Series 3"*, *"punchline"*, *"MacBook Neo"*) kerap memicu kesalahan transkripsi atau pembalikan timestamp pada model AI speech-to-text.
     - Metrik sinkronisasi audio-teks ($\pm 100$ ms) dan kesesuaian gerak bibir (*lip-sync*) berstatus: **Belum terukur secara objektif** karena pengujian dijalankan di lingkungan CLI tanpa instrumen evaluasi perseptual otomatis.

---

### 2.3 Peluang Peningkatan Kecepatan (Profiling & Latensi)

1. **Pemetaan Beban Latensi Pipeline Nyata:**
   - *Bukti Profiling Empiris:*
     - **Video 1 (Fallback APMix DeepSeek):** Total 565,02 detik.
       - Highlight LLM: **306,94 detik (54,3%)**.
       - Render 3 Klip: **256,30 detik (45,4%)** (~1,53 detik render per detik video vertikal).
     - **Video 2 (Run Verifikasi APMix DeepSeek):** Total 511,08 detik.
       - Highlight LLM: **271,72 detik (53,2%)**.
       - Render 3 Klip: **211,08 detik (41,3%)** (Klip 1: 78,65s; Klip 2: 58,49s; Klip 3: 73,94s).
     - **Video 3 (Controlled Replay Gemini Resmi):** Total 243,67 detik (Transkripsi di-bypass via fixture).
       - Highlight LLM (`gemini-3.5-flash-lite`): **9,47 detik (3,9%)** — *Peningkatan kecepatan seleksi AI lebih dari 28× lipat dibandingkan APMix!*
       - Fase Pasca-Highlight (Crop, ASS Burn, Render FFmpeg, Probe): **234,20 detik (96,1%)**.
   - *Analisis:* Ketika provider LLM berkinerja tinggi (seperti Gemini Flash Lite resmi) digunakan, bottleneck seleksi AI hilang sepenuhnya, dan **fase pemrosesan video/render mendominasi 96% total waktu eksekusi**.

2. **Analisis Kritis Akselerasi Hardware (Fakta GPU NVIDIA MX330):**
   - *Spesifikasi Perangkat Uji:* CPU Intel Core i3-1005G1 (2 core / 4 thread), RAM 12 GB nominal, GPU diskret NVIDIA GeForce MX330 (2 GB VRAM).
   - *Fakta Arsitektur Hardware:* Kartu grafis NVIDIA GeForce MX330 berbasis chip GP108 (Pascal/Maxwell refresh). Berdasarkan dokumentasi resmi NVIDIA Video Codec SDK, chip GP108 **tidak memiliki blok hardware encoder NVENC** (hanya mendukung NVDEC decoder dan komputasi CUDA).
   - *Fakta Pipeline Saat Ini:* Deteksi wajah dan kalkulasi crop dilakukan frame per frame di CPU via OpenCV Python sebelum dialirkan ke FFmpeg.
   - *Kesimpulan Teknis:* **Mengusulkan NVENC secara otomatis pada perangkat ini adalah kesalahan teknis mendasar**, karena encoder NVENC tidak didukung secara fisik oleh GPU MX330. Upaya memaksakan flag `-c:v h264_nvenc` akan langsung menghasilkan error `Cannot load nvcuda.dll` atau `Driver does not support the required nvenc API version`.

3. **Ketiadaan Rincian Terpisah pada Fase Render Pasca-Highlight:**
   - *Fakta:* Durasi 234,20 detik pada Video 3 mencakup: pembacaan video OpenCV, eksekusi model deteksi wajah, kalkulasi bounding box, pemotongan video FFmpeg, pembakaran subtitle filter `subtitles` ASS, ekspor berkas VTT, serta verifikasi durasi.
   - *Status Pengukuran:* Porsi waktu masing-masing sub-tahap tersebut saat ini **belum terukur secara terpisah** dalam log aplikasi, sehingga optimasi render harus dimulai dari penambahan stopwatch profiling per sub-tahap.

---

## 3. Prioritas Tiga Perbaikan Berikutnya

Tiga perbaikan diurutkan secara obyektif berdasarkan matriks: **dampak langsung, estimasi usaha, risiko regresi, dan manfaat nyata operasional**.

```
+---------------------------------------------------------------------------------------------------+
| Matriks Prioritas:                                                                                |
| 1. Sanitizer Runtime Timestamp Transkripsi & Harmonisasi Cue ASS/VTT  [Dampak: TINGGI, Usaha: RDH]|
| 2. Heuristik Framing Auto-Crop Multi-Speaker & Safe Area Protection   [Dampak: TINGGI, Usaha: SDNG]|
| 3. Profiling Granular Fase Render & Optimasi Loop CPU/OpenCV          [Dampak: SEDANG, Usaha: RDH]|
+---------------------------------------------------------------------------------------------------+
```

### Prioritas 1: Runtime Sanitizer Timestamp Transkripsi & Harmonisasi Cue Subtitle (ASS vs VTT)
- **Kategori:** Bug Teknis & Kerapuhan Arsitektur.
- **Rasional & Manfaat Nyata:**
  - Menghilangkan penyebab utama kegagalan fatal pada Video 2 dan Video 3.
  - Memastikan pipeline kebal terhadap glitch upstream model STT (kata terbalik, timestamp mundur, atau halusinasi waktu loncat) pada audio panjang maupun dialog alih bahasa (code-switching).
  - Menyelaraskan konstanta chunk size subtitle di `clipper.py` (menyamakan target pembagian kata menjadi satu standar konsisten) agar cue pada video burned-in dan berkas WebVTT identik.
- **Tingkat Usaha:** **Rendah – Sedang**. Logika sanitasi heuristik dan suite 23 unit test sudah terbukti pada evaluasi Video 2 dan Video 3; tinggal diintegrasikan secara resmi ke dalam kode produksi `gemini_transcriber.py` dan `clipper.py`.
- **Risiko Regresi:** **Sangat Rendah**. Mekanisme hanya menyortir dan membersihkan anomali tanpa mengubah teks transkrip sah; suite 108 tes repositori menjadi jaring pengaman.

---

### Prioritas 2: Heuristik Framing Auto-Crop Multi-Speaker & Proteksi Safe Area
- **Kategori:** Kualitas Hasil Editorial.
- **Rasional & Manfaat Nyata:**
  - Menyelesaikan temuan fatal pada Video 2 (kamera menyorot meja kosong di wide shot podcast) dan Video 1 (teks diagram B-roll terpotong di tepi crop vertikal).
  - Tanpa memerlukan modul AI voice-tracking yang berat, perbaikan dapat dicapai melalui heuristik cerdas:
    1. Jika terdeteksi $\ge 2$ wajah dalam frame (wide shot), gunakan crop yang mempertahankan kedua wajah jika memungkinkan, atau pilih wajah yang paling dekat ke safe-center dengan transisi posisi yang di-smooth (*exponential moving average*).
    2. Cegah crop melompat ke koordinat default (tengah layar) jika pada frame sebelumnya terdapat subjek yang stabil.
    3. Terapkan margin pengaman (*safe area padding*) horizontal agar wajah atau teks di tepi frame tidak terpotong habis.
- **Tingkat Usaha:** **Sedang**. Memerlukan penyesuaian matematika crop dan smoothing pada modul deteksi wajah OpenCV.
- **Risiko Regresi:** **Sedang**. Perlu pengujian komparatif untuk memastikan crop pada video talking head 1 orang (seperti Video 1) tetap presisi dan tidak bergoyang (*jitter*).

---

### Prioritas 3: Profiling Granular Fase Render & Optimasi Loop CPU/OpenCV (Tanpa NVENC)
- **Kategori:** Peningkatan Kecepatan / Efisiensi.
- **Rasional & Manfaat Nyata:**
  - Fase render mendominasi 41–45% waktu pada Video 1–2 dan 96% waktu pada Video 3 (234 detik).
  - Menolak asumsi NVENC karena keterbatasan hardware GPU MX330 (GP108), dan memfokuskan peningkatan performa pada jalur yang terbukti:
    1. Menyematkan instrumen logging waktu presisi per sub-tahap (durasi OpenCV baca frame, durasi deteksi wajah Haar Cascade, durasi filter ASS, durasi encoding x264 FFmpeg).
    2. Mengoptimalkan deteksi wajah OpenCV: daripada mendeteksi wajah di setiap frame (25–30 fps), jalankan deteksi setiap $N$ frame (misal setiap 5–10 frame) lalu interpolasikan koordinat crop, yang berpotensi memangkas beban CPU secara drastis tanpa mengurangi kualitas visual.
- **Tingkat Usaha:** **Rendah – Sedang**. Menambahkan stopwatch logging dan sampling frame deteksi di `clipper.py` / `video_cropper.py`.
- **Risiko Regresi:** **Sangat Rendah**. Tidak mengubah format kontainer maupun decoding video; hanya mengatur frekuensi eksekusi cascade detector.

---

## 4. Rekomendasi Pekerjaan Pertama

Sebagai langkah tindak lanjut yang paling rasional, terisolasi, dan berdampak langsung sebelum melangkah ke modifikasi visual atau performa yang lebih luas, direkomendasikan pekerjaan pertama berikut untuk diputuskan oleh pengguna:

### **Pekerjaan Rekomendasi: Integrasi Runtime Timestamp Sanitizer Transkripsi & Harmonisasi Cue ASS/VTT**

#### A. Ruang Lingkup Pekerjaan (Scope)
1. **Integrasi Heuristic Timestamp Sanitizer ke Kode Produksi:**
   - Memindahkan logika *bounded recovery* dan penanganan anomali offset kata terbalik dari skrip scratch evaluasi ke modul produksi `shorts_generator/local/gemini_transcriber.py`.
   - Mengganti pelemparan exception kaku `ValueError` pada baris 365 dengan pemulihan cerdas: jika `end_offset < start_offset`, tukar atau sesuaikan nilai end offset secara monoton naik berdasarkan kata sekitar, dan beri penandaan log diagnostik tanpa menggagalkan job.
   - Mengeliminasi lonjakan halusinasi waktu liar yang melebihi durasi fisik media.
2. **Harmonisasi Konstanta Cue Subtitle:**
   - Menyelaraskan target pengelompokan kata subtitle di `shorts_generator/clipper.py` sehingga pembentukan cue untuk filter hardcoded ASS dan ekspor soft-subtitle WebVTT menggunakan konstanta yang sama (menghilangkan perbedaan chunk 4 kata vs 5 kata).
3. **Penyempurnaan Suite Pengujian Regresi:**
   - Menambahkan unit test baru di `tests/test_v2_transcript_regression.py` yang memvalidasi bahwa payload transkrip 5.851 kata Video 3 (berisi 28 kata cacat) dapat diproses hingga menghasilkan segmen valid secara otomatis di tingkat modul produksi.

#### B. Kriteria Selesai (Done Criteria)
1. **Kebal Anomali Transkrip:** Modul `gemini_transcriber.py` mampu memproses transkrip mentah yang memiliki kata terbalik (`end < start`) maupun lompatan waktu non-monotonik tanpa melempar exception `ValueError` dan tanpa memicu fallback model yang tidak diinginkan.
2. **Kesesuaian Cue Subtitle 100%:** Berkas WebVTT dan berkas subtitle ASS yang dihasilkan untuk klip uji memiliki jumlah cue dan rentang interval waktu kata yang persis sama.
3. **Lolos Suite Pengujian Penuh:** Seluruh unit test repositori (108 tes baseline + tes sanitizer baru) lulus 100% (`exit code 0`, 0 failure, 0 error).
4. **Preservasi Arsitektur:** Tidak ada penambahan dependensi pihak ketiga baru, tidak ada modifikasi pada konfigurasi API eksternal, dan seluruh aset cache historis (Video 1–3) tetap utuh.

---

*Dokumen ini disusun sebagai dasar keputusan teknis resmi sebelum implementasi kode berikutnya disetujui.*
