# LAPORAN EKSEKUSI CONTROLLED REPLAY VIDEO 3 (API RESMI)

**Tanggal Eksekusi:** 2026-09-30  
**Status Eksekusi:** COMPLETED (Kelulusan Teknis Pipeline: LULUS)  
**Runner:** `scratch/run_controlled_replay_v3_official.py`  
**Provider Digunakan:** Google Gemini API Resmi  
**Baseline Kode:** `main`  

---

## 1. Ringkasan Eksekusi

| Parameter | Nilai Tercatat |
| :--- | :--- |
| **Job ID** | `val_v3_official_35336` |
| **Session Folder** | `output_val_v3/20260930_092900_val_v3_official_35336` |
| **Waktu Mulai** | `2026-09-30T09:29:00.615339+07:00` |
| **Waktu Berakhir** | `2026-09-30T09:33:04.287463+07:00` |
| **Durasi Total (Wall-Clock)** | 243,67 detik (~4 menit) |
| **Durasi Inferensi LLM** | 9,47 detik (4 panggilan inferensi tuntas) |
| **Durasi Fase Setelah Analisis Highlight** | 234,20 detik (mencakup pemotongan klip, re-frame vertikal, pembakaran subtitle ASS, ekspor VTT, verifikasi durasi, dan finalisasi berkas) |
| **Status Biaya API** | **Belum terverifikasi dari billing** (Model `gemini-3.5-flash-lite` memiliki ketentuan Free Tier, namun label Free Tier pada runner/job bukan merupakan bukti tagihan aktual Rp0 dari konsol Google Cloud Billing) |
| **Status Pekerjaan** | `completed` |
| **Tahapan Terakhir** | `completed` |

---

## 2. Parameter Provider & Endpoint Resmi

| Parameter | Konfigurasi | Status Verifikasi |
| :--- | :--- | :--- |
| **Provider** | `gemini` | Google Generative Language API Resmi |
| **Endpoint Base URL** | `https://generativelanguage.googleapis.com/v1beta/openai/` | Resmi OpenAI-Compatible Endpoint |
| **Model** | `gemini-3.5-flash-lite` | Didukung resmi oleh endpoint |
| **Variabel Kunci** | `GEMINI_API_KEY` | Terbaca dari berkas `.env` lokal |
| **Konteks Token** | Hingga 1.000.000 token | Menampung transkrip chunk (~8.800 token) tanpa kendala payload |
| **Batas Waktu SDK** | 600 detik per request | Ditegakkan (selesai dalam <4 detik per request) |
| **Batas Anggaran Job** | 1.800 detik | Ditegakkan (selesai dalam 243,67 detik) |

---

## 3. Catatan Penghitung API (Guards & Concurrency Counters)

| Kategori API | Attempted | Dispatched | Success | Failed | Blocked | Pagu Maksimal |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **STT Gemini (Transcribe)** | 0 | 0 | 0 | 0 | 0 | **0 (Hard-blocked)** |
| **Google File API Upload** | 0 | 0 | 0 | 0 | 0 | **0 (Hard-blocked)** |
| **Highlight Inference** | 4 | 4 | 4 | 0 | 0 | **4** |

### Analisis Guard & Kepatuhan
1. **Perlindungan Biaya Transkripsi:**
   - 0 pemanggilan ke endpoint transkripsi dan 0 unggahan ke File API.
   - Seluruh transkrip dipasok dari berkas diagnostik lokal yang telah tersimpan (`diagnostic_transcript_pre_validation_val_v3_long_72842.json`, SHA-256: `5c0342f3...`).
2. **Performa Inferensi Highlight:**
   - Request 1 (Deteksi densitas & tipe konten): 1,05 detik (`podcast`, `density: medium`).
   - Request 2 (Chunk 1 - detik 0..1260): 3,52 detik (6 kandidat).
   - Request 3 (Chunk 2 - detik 1140..2400): 2,79 detik (6 kandidat).
   - Request 4 (Chunk 3 - detik 2280..2631): 2,10 detik (3 kandidat).
   - Total waktu komputasi LLM adalah 9,47 detik untuk seluruh transkrip 43 menit.

---

## 4. Hasil Sanitasi Transkrip & Evaluasi Rentang Aman

- **Total Kata Mentah / Ter-sanitasi:** 5.851 kata
- **Kata Direcovery (Bounded Recovery):** 3 kata (rentang `hyper-arousal` pada detik 512,6s - 514,6s)
- **Rentang Tidak Tepercaya (Untrusted Spans):** 5 rentang (total 34,1 detik, atau 1,296% dari media)
- **Validitas Kontrak:** `True` (seluruh kandidat klip terpilih berada di luar rentang cacat waktu)

---

## 5. Hasil Seleksi Highlight & 3 Klip Terpilih (Keluaran Model AI)

> [!NOTE]
> Skor viralitas, judul, hook, dan alasan viralitas di bawah ini adalah **murni keluaran estimasi model AI (LLM)** berdasarkan pembacaan teks transkrip. Nilai ini bukan hasil pengujian terhadap penonton riil dan bukan bukti audit audio yang telah didengarkan.

| No | File Klip | Rentang Waktu Sumber | Durasi Klip | Skor Viral AI | Judul AI | Hook Sentence (Teks Keluaran AI) |
| :-: | :--- | :---: | :---: | :---: | :--- | :--- |
| 1 | `short_01.mp4` | 23,8s - 43,3s | 19,486s | **95** | Analogi Trauma yang Diperban | *"Bayangin lu jatuh, luka, terus infeksi, tapi bukannya dibersihin dulu, malah langsung ditambel aja lukanya pakai perban."* |
| 2 | `short_02.mp4` | 2164,1s - 2201,6s | 37,471s | **95** | Transformasi Reaksi Trauma | *"Begitu aku bangun, aku enggak lagi punya respon kayak kesal atau marah, responnya adalah oke itu terjadi dan bisa senyum."* |
| 3 | `short_03.mp4` | 476,0s - 506,8s | 30,800s | **92** | Trauma Tersimpan di Dalam Badan | *"Jadi itu respon di mana mungkin kita secara memorinya enggak ingat, tapi badan kita yang nyimpen."* |

---

## 6. Verifikasi Fisik Media & Subtitle

Ketiga klip video berformat vertikal 9:16 (404x720) telah dirender dan diuji integritas bitstream-nya melalui FFmpeg Full Decode Test (`ffmpeg -v error -i ... -f null -`):

| Berkas Video | Ukuran File | Format & Resolusi | Codec Video / Audio | Durasi Hasil vs Target | FFmpeg Null Decode | Subtitle VTT (Sidecar) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`short_01.mp4`** | 1.726.777 byte (~1,65 MB) | MP4 (404x720) | H.264 / AAC 44,1 kHz | 19,486s (target: 19,5s, Δ: -0,014s) | **Exit Code 0 (0 error)** | `short_01.vtt` (8 cues) |
| **`short_02.mp4`** | 3.231.869 byte (~3,08 MB) | MP4 (404x720) | H.264 / AAC 44,1 kHz | 37,471s (target: 37,5s, Δ: -0,029s) | **Exit Code 0 (0 error)** | `short_02.vtt` (14 cues) |
| **`short_03.mp4`** | 4.000.833 byte (~3,82 MB) | MP4 (404x720) | H.264 / AAC 44,1 kHz | 30,800s (target: 30,8s, Δ: 0,000s) | **Exit Code 0 (0 error)** | `short_03.vtt` (16 cues) |

### Perbedaan Teknis Subtitle ASS Terbakar vs Berkas VTT Terpisah
- **Subtitle ASS (Advanced SubStation Alpha):**
  - **Telah dibakar langsung ke frame video MP4 (*hardcoded/burned-in*)** menggunakan filter `subtitles` FFmpeg.
  - Memiliki styling visual TikTok/Reels: Font Arial ukuran 30, warna teks kuning-emas (`&H0015CCFA`), outline hitam tebal (3.5 px), bayangan semi-transparan, dengan margin bawah vertikal 16% dari tinggi video agar tidak tertutup antarmuka aplikasi seluler.
  - Menjadi bagian permanen dari piksel video MP4 dan tidak dapat dimatikan.
- **Berkas WebVTT (`short_0x.vtt`):**
  - Berkas teks terpisah (*sidecar*) yang berisi cue waktu `HH:MM:SS.mmm` dan teks kapital.
  - Berfungsi untuk pratinjau browser atau keperluan pengunggahan takarir tertutup (*closed captions / CC*) opsional di YouTube Studio / platform hosting.

---

## 7. Pemeriksaan Kualitas Klip & Catatan Timestamp

Pemeriksaan dilakukan secara obyektif berdasarkan struktur berkas transkrip, baris cue VTT, dan parameter ffprobe:

### A. Klip 1 (`short_01.mp4` - 19,486s)
- **Awal Potongan (detik 00:00:00.000):** Tepat dimulai pada kata pembuka analogi *"Bayangin lu jatuh, luka, terus infeksi..."*.
- **Akhir Potongan (detik 00:00:19.486):** Cue takarir berakhir di 00:00:18.000 pada kata *"Meskipun di luar keliatannya baik-baik aja."*, lalu ada jeda natural ~1,48 detik sebelum potongan berakhir di 19,486s. Tepat berhenti sebelum kalimat pembicara berikutnya pada detik 43,6s video sumber (*"gua ini ini adalah analogi..."*).
- **Keutuhan Kalimat:** **Utuh dan lengkap.** Gagasan diawali dengan premis dan ditutup dengan kesimpulan yang utuh tanpa kata terpenggal.
- **Kesesuaian Wajah dalam Crop, Keterbacaan Takarir, Sinkronisasi Audio-Visual:**
  - **Status: Belum dinilai secara audiovisual.**
  - **Pemeriksaan Manusia yang Diperlukan:**
    1. Memutar video untuk memastikan wajah pembicara utama tidak terpotong ke samping oleh framing crop vertikal 404x720.
    2. Memastikan takarir ASS warna kuning-emas kontras terhadap latar visual baju/ruangan dan tidak bertabrakan dengan elemen grafis wajah.
    3. Mendengarkan audio untuk memastikan tidak ada bunyi *click/pop* pada sambungan potongan awal/akhir.

### B. Klip 2 (`short_02.mp4` - 37,471s)
- **Awal Potongan (detik 00:00:00.000):** Dimulai dengan interjeksi tanggapan *"Benar. Tapi begitu aku bangun..."* (detik 00:00:00.000 - 00:00:01.400).
- **Masalah Jeda Hening / Tanpa Takarir (Timestamp: 00:00:09.200 - 00:00:18.500):**
  - **Terdeteksi celah sepanjang ~9,3 detik tanpa takarir** antara akhir kalimat *"Responnya adalah adalah oke itu terjadi."* (00:00:09.200) dan awal kalimat berikutnya *"Dan bisa senyum gitu sama pengalaman tersebut..."* (00:00:18.500).
- **Masalah Fragmen Percakapan Menjelang Akhir (Timestamp: 00:00:25.100 - 00:00:34.000):**
  - Terdapat kata terisolasi *"ITU"* (00:00:25.100 - 00:00:25.400), filler *"aku enggak tahu sih enggak tahu ya yang dengar kayak gimana gitu"*, dan interupsi lawan bicara *"Semua apa?"* (00:00:32.400).
- **Akhir Potongan (detik 00:00:37.471):** Cue berakhir di 00:00:35.800 pada *"dibeli pakai uang sih."* diikuti buffer ~1,67 detik. Kalimat penutup selesai, namun struktur tengahnya terfragmentasi.
- **Kesesuaian Wajah dalam Crop, Keterbacaan Takarir, Sinkronisasi Audio-Visual:**
  - **Status: Belum dinilai secara audiovisual.**
  - **Pemeriksaan Manusia yang Diperlukan:**
    1. Memverifikasi isi jeda ~9,3 detik (detik 09.200 - 18.500): apakah ini hening canggung, jeda emosional pembicara, atau dialog lawan bicara yang tidak terambil takarirnya.
    2. Memeriksa perilaku kamera/framing pada detik 32.4 saat terdengar interupsi *"Semua apa?"* (apakah kamera melompat canggung).
    3. Mengevaluasi apakah jeda 9,3 detik menurunkan retensi penonton secara drastis.

### C. Klip 3 (`short_03.mp4` - 30,800s)
- **Masalah Fragmen Menggantung di Awal (Timestamp: 00:00:00.000 - 00:00:04.900):**
  - **Klip diawali dengan potongan kalimat sebelum hook utama:** *"Dan juga biasanya ditandai dengan ada yang namanya Andre."* (detik 00:00:00.000 - 00:00:04.900).
  - Hook utama yang ditargetkan (*"Jadi itu respon di mana mungkin kita secara memorinya enggak ingat, tapi badan kita yang nyimpen."*) baru dimulai pada detik **00:00:05.000**.
  - Dampak: 5 detik awal klip terdengar menggantung dan membingungkan penonton jika tidak dipotong.
- **Akhir Potongan (detik 00:00:30.800):** Cue berakhir di 00:00:28.900 pada kata *"trauma yang kita alamin."* dengan buffer ~1,9 detik. Potongan berhenti tepat sebelum lawan bicara merangkum di detik 507,0s video sumber (*"kalau boleh gua rangkum ya..."*). Kalimat penutup utuh.
- **Kesesuaian Wajah dalam Crop, Keterbacaan Takarir, Sinkronisasi Audio-Visual:**
  - **Status: Belum dinilai secara audiovisual.**
  - **Pemeriksaan Manusia yang Diperlukan:**
    1. Memeriksa apakah 5 detik awal (00:00:00 - 00:00:05) perlu dipangkas manual agar video langsung menyengat penonton di detik pertama dengan hook *"Jadi itu respon..."*.
    2. Memeriksa pergerakan wajah pada crop vertikal selama pembicara menjelaskan respons trauma tubuh.
    3. Mendengarkan sinkronisasi audio dan intonasi pembicara.

---

## 8. Catatan Teknis & Koreksi Riwayat Kegagalan Provider Terdahulu

Berdasarkan pemeriksaan metadata berkas job terdahulu pada direktori `output_val_v3/`, dicatat kronologi faktual sebagai berikut:

1. **OpenAI API Resmi (`job_val_v3_official_92249`):**
   - Mengalami HTTP 429 (`insufficient_quota` / `credit_balance_exhausted`) pada detik ke-2,62 karena saldo akun $0.
2. **Groq API Resmi (`job_val_v3_official_34393`):**
   - Mengalami **HTTP 429** (`RateLimitError: Rate limit reached for model openai/gpt-oss-120b on tokens per minute (TPM): Limit 8000, Used 7946, Requested 7006. Please try again in 52.14s`).
   - *Koreksi Fakta:* Kesalahan ini adalah HTTP 429 rate limit token per menit (TPM), bukan HTTP 413, dan terjadi pada model `openai/gpt-oss-120b`.
3. **APMix Proxy (`job_val_v3_replay_33367`):**
   - Mengalami **HTTP 503** (`upstream_unavailable: The model is temporarily unavailable. Retry in a moment`) pada permintaan Chunk 2 setelah berjalan selama **sekitar 302,25 detik** (dispatched pada t=299,16s, terminated pada t=601,41s).
   - *Koreksi Fakta:* Dugaan bahwa kegagalan disebabkan oleh batas gateway timeout 300 detik pada proxy APMix adalah **hipotesis yang belum terbukti secara definitif**, karena galat resmi dari server hanya menyatakan `upstream_unavailable`.
4. **Google Gemini API Resmi (`job_val_v3_official_35336`):**
   - Menyelesaikan 4 permintaan inferensi highlight dalam tempo 9,47 detik tanpa galat kuota dan menghasilkan struktur JSON yang valid.

---

## 9. Verifikasi Preservasi Berkas Terproteksi (68 Berkas)

Snapshot integritas SHA-256 dievaluasi sebelum dan sesudah eksekusi:
- **65 berkas output Validasi Video 1 dan Video 2:** 100% Utuh (SHA-256 identik)
- **Berkas `.env`:** 100% Utuh
- **Source media Video 3 (`output_val_v3/source_long_v3.mp4`):** 100% Utuh (`d4e1d8bc...`)
- **Fixture transkrip diagnostik Video 3:** 100% Utuh (`5c0342f3...`)

Hasil audit preservasi: **`Preserved files intact: True` (0 berkas terhapus / 0 regresi).**

---

## 10. Keputusan Evaluasi

Ditetapkan dua keputusan terpisah:

### A. Keputusan Kelulusan Teknis Pipeline: LULUS (PASS)
- Pipeline berhasil mengeksekusi transkrip video panjang (43 menit, 5.851 kata) secara stabil.
- Guard isolasi biaya bekerja sempurna (0 pemanggilan STT Gemini, 0 pemanggilan File API).
- 4/4 inferensi highlight LLM terselesaikan tanpa error sintaksis.
- Seluruh 3 klip video MP4 vertikal 9:16 berhasil dipotong, di-crop, dan dibakar subtitle ASS dengan status lolos uji integritas FFmpeg full decode (`exit code 0`, 0 frame rusak).
- Seluruh 68 berkas terproteksi terjaga 100% utuh.

### B. Keputusan Kesiapan Publikasi Tiap Klip:
1. **Klip 1 (`short_01.mp4`): KANDIDAT KUAT (Memerlukan Verifikasi Audiovisual Manusia)**
   - Kalimat utuh dan padat, hook analogi langsung muncul di detik pertama. Siap dipublikasikan segera setelah manusia memverifikasi framing wajah dan keterbacaan takarir pada layar ponsel.
2. **Klip 2 (`short_02.mp4`): PERLU PENINJAUAN EDITORIAL (Hold)**
   - Belum siap dipublikasikan langsung karena terdapat jeda hening / tanpa takarir selama ~9,3 detik di tengah klip (detik 09.200 - 18.500) dan adanya kata-kata filler di akhir. Perlu diputuskan secara editorial apakah jeda tersebut layak dipertahankan atau harus dipadatkan.
3. **Klip 3 (`short_03.mp4`): PERLU TRIM AWALAN (Hold)**
   - Belum siap dipublikasikan langsung karena memiliki fragmen kalimat menggantung sepanjang 5 detik di awal (00:00:00 - 00:00:05). Disarankan memangkas 5 detik pertama agar video langsung diawali hook utama di detik 00:05.
