# LAPORAN EVALUASI VALIDASI VIDEO 3 DAN KESIAPAN PUBLIKASI

**Dokumen:** Laporan Akhir Evaluasi Validasi Video 3 & Kesiapan Publikasi  
**ID Pekerjaan (Job ID):** `val_v3_official_35336`  
**Folder Sesi:** `output_val_v3/20260930_092900_val_v3_official_35336`  
**Tanggal Evaluasi:** 2026-09-30  
**Baseline Kode:** `main` (Branch tanpa modifikasi kode produksi)  
**Status Kelulusan Teknis Pipeline:** **LULUS (PASS)** untuk run ini  

---

## 1. Ringkasan Eksekutif

Controlled replay validasi Video 3 (podcast durasi panjang 43 menit 50 detik / 2.630,65 detik) telah berhasil dieksekusi secara penuh hingga menghasilkan 3 klip video vertikal 9:16 dengan takarir terbakar (*burned-in* ASS) dan takarir terpisah (WebVTT).

### Poin Kunci Hasil Eksekusi:
1. **Kelulusan Teknis Pipeline:** Pipeline dinyatakan **lulus untuk run ini**. Seluruh alur berjalan deterministik dengan total durasi *wall-clock* 243,67 detik (~4 menit), 4 inferensi highlight LLM terselesaikan tanpa error sintaksis, ketiga berkas MP4 lolos uji decode penuh FFmpeg (`exit code 0`), dan 68 berkas terproteksi tetap utuh 100%.
2. **Pemisahan Durasi Fase:** Sekitar **9,47 detik** dialokasikan untuk fase inferensi highlight oleh LLM. Sekitar **234,20 detik** merupakan **fase setelah highlight** (mencakup pemotongan klip sumber, deteksi wajah/re-framing vertikal 9:16, pembakaran takarir ASS, ekspor VTT, verifikasi durasi, dan finalisasi berkas). Durasi 234,20 detik ini bukan merupakan pengukuran FFmpeg murni karena belum ada instrumen pengukur per sub-tahap.
3. **Status Biaya API:** Dicatat resmi sebagai **“belum terverifikasi dari billing”**. Model `gemini-3.5-flash-lite` yang digunakan memiliki ketentuan Free Tier dari Google, namun label Free Tier pada kode runner/job bukan merupakan bukti tagihan aktual Rp0 dari konsol Google Cloud Billing.
4. **Status Evaluasi Audiovisual & Publikasi:** Karena lingkungan evaluasi berupa antarmuka baris perintah (*headless/CLI*) tanpa perangkat pemutar grafis dan audio, seluruh klip diberi status **“Belum dinilai secara audiovisual”**. Tidak ada klip yang diklaim "siap tayang" hanya berdasarkan metadata. Kesiapan publikasi memerlukan verifikasi manusia melalui checklist yang disediakan.

---

## 2. Parameter Teknis & Hasil Verifikasi

### Tabel Ringkasan Metrik Pekerjaan

| Parameter | Nilai Tercatat / Bukti | Keterangan |
| :--- | :--- | :--- |
| **Job ID** | `val_v3_official_35336` | Sesi Controlled Replay Video 3 Resmi |
| **Media Sumber** | `output_val_v3/source_long_v3.mp4` | Durasi: 2.630,658s (~43,8 menit), SHA-256: `d4e1d8bc...` |
| **Fixture Transkrip** | `diagnostic_transcript_pre_validation_val_v3_long_72842.json` | 5.851 kata mentah, SHA-256: `5c0342f3...` |
| **Durasi Total Eksekusi** | 243,67 detik | Waktu mulai: 09:29:00, Selesai: 09:33:04 |
| **Fase Inferensi Highlight** | 9,47 detik | 4/4 request sukses (1 klasifikasi + 3 chunk) |
| **Fase Setelah Highlight** | 234,20 detik | Pemotongan, reframe, burn ASS, VTT, validasi |
| **Panggilan Transkripsi (STT)**| 0 attempted / 0 dispatched | Terkunci guard (pagu: 0) |
| **Unggahan File API** | 0 upload / 0 polling | Terkunci guard (pagu: 0) |
| **Preservasi Aset** | 68 dari 68 berkas utuh | 65 berkas V1/V2, `.env`, master video, fixture |

### Tabel Verifikasi Media Fisik

| Berkas Klip | Durasi Probed vs Target | Resolusi & Rasio | Codec Video / Audio | FFmpeg Null Decode | Format Takarir Terbakar | Berkas Takarir Terpisah |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`short_01.mp4`** | 19,486s (target: 19,5s) | 404x720 (9:16) | H.264 / AAC 44,1 kHz | Exit Code 0 (0 error) | ASS hardcoded (TikTok-style) | `short_01.vtt` (8 cues) |
| **`short_02.mp4`** | 37,471s (target: 37,5s) | 404x720 (9:16) | H.264 / AAC 44,1 kHz | Exit Code 0 (0 error) | ASS hardcoded (TikTok-style) | `short_02.vtt` (14 cues) |
| **`short_03.mp4`** | 30,800s (target: 30,8s) | 404x720 (9:16) | H.264 / AAC 44,1 kHz | Exit Code 0 (0 error) | ASS hardcoded (TikTok-style) | `short_03.vtt` (16 cues) |

> [!IMPORTANT]
> **Pembedaan Takarir ASS vs WebVTT:**
> - **Takarir ASS (Advanced SubStation Alpha):** Telah dibakar (*hardcoded / burned-in*) secara permanen ke frame visual MP4 menggunakan filter `subtitles` FFmpeg dengan gaya font Arial kuning-emas (`&H0015CCFA`), garis tepi hitam tebal 3.5 px, dan margin bawah 16% tinggi video. Takarir ini tidak bisa dinonaktifkan di pemutar video.
> - **Berkas WebVTT (`.vtt`):** Berkas teks terpisah (*sidecar*) berisi blok timestamp `HH:MM:SS.mmm` yang diperuntukkan bagi pratinjau browser atau pengunggahan *closed caption* (CC) terpisah di platform media sosial.

---

## 3. Riwayat Provider & Rekonsiliasi Kegagalan Terdahulu

Pemeriksaan metadata job terdahulu pada direktori `output_val_v3/` menunjukkan catatan faktual berikut:

| Provider & Runner | Job ID & Waktu | Status | Galat Faktual / Bukti | Koreksi & Catatan Analisis |
| :--- | :--- | :---: | :--- | :--- |
| **OpenAI API Resmi** | `val_v3_official_92249`<br>(2026-09-29) | Failed | **HTTP 429** (`credit_balance_exhausted` / `insufficient_quota`) | Akun valid (HTTP 200 pada probing model), namun saldo kredit $0. Berhenti fail-fast pada detik ke-2,62. |
| **Groq API Resmi** | `val_v3_official_34393`<br>(2026-09-30) | Failed | **HTTP 429** (`Rate limit reached for model openai/gpt-oss-120b on tokens per minute (TPM): Limit 8000, Used 7946, Requested 7006. Please try again in 52.14s`) | **Koreksi Fakta:** Galat adalah **HTTP 429** (batas TPM terlampaui pada model `openai/gpt-oss-120b`), **bukan HTTP 413**. Payload chunk (~8.800 token) melebihi batas 8.000 TPM Groq Free Tier. |
| **APMix Proxy** | `val_v3_replay_33367`<br>(2026-09-30) | Failed | **HTTP 503** (`upstream_unavailable: The model is temporarily unavailable. Retry in a moment`) pada Chunk 2 | Permintaan Chunk 2 dikirim pada t=299,16s dan putus pada t=601,41s (**durasi panggilan ~302,25 detik**). Dugaan batas gateway proxy 300 detik hanya merupakan **hipotesis**, bukan penyebab yang terbukti definitif. |
| **Google Gemini Resmi** | `val_v3_official_35336`<br>(2026-09-30) | Completed | **Sukses 100%** (4 panggilan tuntas dalam 9,47 detik) | Endpoint OpenAI-compatible Google Generative Language dengan model `gemini-3.5-flash-lite`. Mampu memproses chunk transkrip besar tanpa error payload. |

---

## 4. Evaluasi Editorial Per Klip & Titik Pemeriksaan Timestamp

> [!NOTE]
> Judul, teks hook, dan skor viralitas (95, 95, 92) yang tercantum di bawah ini adalah **murni keluaran estimasi model AI (LLM)** berdasarkan analisis teks transkrip. Nilai ini bukan hasil pengujian penonton riil, bukan hasil tes tayang, dan bukan hasil audit audio yang didengar.

### Klip 1 (`short_01.mp4`)
- **Metadata AI:** Judul: *"Analogi Trauma yang Diperban"* | Skor AI: **95** | Durasi: 19,486s (Rentang Sumber: 23,8s – 43,3s)
- **Teks Hook Keluaran AI:** *"Bayangin lu jatuh, luka, terus infeksi, tapi bukannya dibersihin dulu, malah langsung ditambel aja lukanya pakai perban."*
- **Analisis Timestamp VTT & Batas Potongan:**
  - **Awal Potongan (00:00:00.000):** Tepat dimulai pada kata pembuka analogi (*"Bayangin lu jatuh, luka, terus infeksi..."*).
  - **Akhir Potongan (00:00:19.486):** **Cue takarir terakhir berakhir pada 00:00:18.000** dari total durasi 19,486 detik (terdapat buffer natural ~1,48 detik). Berhenti tepat sebelum kalimat pembicara berikutnya pada detik 43,6s video sumber (*"gua ini ini adalah analogi..."*).
  - **Keutuhan Kalimat:** Kalimat sangat utuh, diawali analogi luka dan diakhiri kesimpulan kalimat yang selesai sempurna tanpa kata terpenggal.
- **Status Evaluasi Audiovisual:** **Belum dinilai secara audiovisual.**
- **Pemeriksaan Manusia yang Masih Diperlukan:**
  - [ ] **Framing Wajah:** Periksa apakah wajah pembicara utama berada tepat di tengah area crop vertikal 9:16 (404x720) dan tidak terpotong saat bergerak.
  - [ ] **Kontras Takarir:** Pastikan teks takarir ASS warna kuning-emas terbaca jelas terhadap warna pakaian pembicara atau latar belakang video.
  - [ ] **Akhir Ucapan & Audio:** Dengarkan akhir ucapan di sekitar 00:18.000–00:19.486 untuk memastikan intonasi kata penutup terdengar natural dan tidak ada bunyi pemotongan (*pop/click*).

---

### Klip 2 (`short_02.mp4`)
- **Metadata AI:** Judul: *"Transformasi Reaksi Trauma"* | Skor AI: **95** | Durasi: 37,471s (Rentang Sumber: 2164,1s – 2201,6s)
- **Teks Hook Keluaran AI:** *"Begitu aku bangun, aku enggak lagi punya respon kayak kesal atau marah, responnya adalah oke itu terjadi dan bisa senyum."*
- **Analisis Timestamp VTT & Batas Potongan:**
  - **Awal Potongan (00:00:00.000):** Dimulai dengan kata interjeksi tanggapan terhadap lawan bicara (*"Benar. Tapi begitu aku bangun..."*).
  - **Titik Kritis Celah Takarir (00:00:09.200 – 00:00:18.500):** **Tidak ada cue takarir pada rentang 00:09,200 hingga 00:18,500 (~9,3 detik).** *Catatan Faktual: Celah ini adalah ketiadaan cue takarir dalam berkas VTT. Jangan menyebut celah cue ini sebagai hening audio sebelum didengarkan langsung oleh manusia (bisa jadi berisi ucapan lawan bicara yang tidak ter-subtitle, musik pengiring, atau hening jeda pembicara).*
  - **Titik Kritis Filler & Interupsi (00:00:25.100 – 00:00:35.800):** Memuat kata terisolasi *"ITU"* (00:25,100), filler *"aku enggak tahu sih enggak tahu ya yang dengar kayak gimana gitu"*, interupsi lawan bicara *"Semua apa?"* (00:32,400), lalu ditutup *"Itu benar-benar enggak bisa dibeli pakai uang sih."* (00:35,800).
- **Status Evaluasi Audiovisual:** **Belum dinilai secara audiovisual.**
- **Pemeriksaan Manusia yang Masih Diperlukan:**
  - [ ] **Verifikasi Audio Celah 00:09,200–00:18,500:** Dengarkan apa yang terjadi selama 9,3 detik tersebut: apakah ada suara pembicara, suara lawan bicara, atau hening canggung yang dapat menjatuhkan retensi penonton.
  - [ ] **Evaluasi Visual Interupsi (00:25,100–00:35,800):** Periksa perpindahan framing kamera saat lawan bicara menginterupsi *"Semua apa?"* pada detik 32,4.
  - [ ] **Keputusan Editorial:** Tentukan apakah klip ini perlu dipangkas (*jump cut*) pada celah 9 detik tersebut sebelum layak dipublikasikan.

---

### Klip 3 (`short_03.mp4`)
- **Metadata AI:** Judul: *"Trauma Tersimpan di Dalam Badan"* | Skor AI: **92** | Durasi: 30,800s (Rentang Sumber: 476,0s – 506,8s)
- **Teks Hook Keluaran AI:** *"Jadi itu respon di mana mungkin kita secara memorinya enggak ingat, tapi badan kita yang nyimpen."*
- **Analisis Timestamp VTT & Batas Potongan:**
  - **Titik Kritis Pengantar Awal (00:00:00.000 – 00:00:04.900):** **Bagian 00:00,000–00:04,900 berisi pengantar sebelum hook utama.** Kata pembukanya adalah sisa kalimat dari topik sebelumnya: *"Dan juga biasanya ditandai dengan ada yang namanya Andre."* Hook utama yang ditargetkan AI (*"Jadi itu respon di mana mungkin kita secara memorinya enggak ingat..."*) baru dimulai pada sekitar **00:05,000**.
  - **Akhir Potongan (00:00:30.800):** Cue berakhir di 00:00:28.900 pada kata *"trauma yang kita alamin."* (buffer ~1,9 detik). Potongan berakhir tepat sebelum lawan bicara mulai merangkum di detik 507,0s video sumber (*"kalau boleh gua rangkum ya..."*).
- **Status Evaluasi Audiovisual:** **Belum dinilai secara audiovisual.**
- **Pemeriksaan Manusia yang Masih Diperlukan:**
  - [ ] **Uji Potong Awalan (00:00–00:05):** Tonton dan dengarkan 5 detik pertama untuk menguji apakah pemotongan awal langsung ke detik 00:05,000 membuat hook lebih menyengat tanpa memotong kata yang sedang diucapkan.
  - [ ] **Framing Pembicara:** Periksa apakah kamera menyorot Andre atau pembicara lain selama penjelasan respons trauma tubuh.
  - [ ] **Kelancaran Penutup:** Pastikan potongan di 00:30.800 tidak memotong awalan suara lawan bicara yang masuk di detik 507,0s.

---

## 5. Dua Keputusan Terpisah

### A. Keputusan Kelulusan Teknis Pipeline: LULUS (PASS)
Pipeline ShortsStudio dinyatakan **lulus secara teknis untuk eksekusi run ini** berdasarkan bukti obyektif:
1. **Stabilitas Eksekusi Panjang:** Berhasil memproses transkrip podcast 43 menit (5.851 kata) dan membaginya ke dalam 3 chunk tanpa kegagalan memori maupun pembatalan waktu.
2. **Kepatuhan Guard Biaya:** Panggilan STT Gemini dan Google File API upload tercatat 0 (terkunci guard 100%), mencegah kebocoran biaya transkripsi ulang.
3. **Kepatuhan Kontrak Inferensi:** 4/4 pemanggilan inferensi highlight ke Google Gemini API resmi tuntas dengan output JSON valid dalam waktu 9,47 detik.
4. **Validitas Media Fisik:** Seluruh 3 berkas MP4 berhasil dirender dengan takarir ASS dan lolos uji integritas FFmpeg full decode (`exit code 0`, 0 frame rusak).
5. **Preservasi Aset:** 68 berkas terproteksi (termasuk artefak Video 1 dan Video 2) terverifikasi 100% utuh tanpa perubahan hash SHA-256.

### B. Keputusan Kesiapan Publikasi Editorial Tiap Klip:
Berdasarkan prinsip kehati-hatian teknis dan ketiadaan verifikasi sensoris di lingkungan CLI: **Tidak ada klip yang diklaim "siap tayang" langsung ke publik hanya berdasarkan metadata.** Rekomendasi editorial untuk masing-masing klip adalah:

1. **Klip 1 (`short_01.mp4`): KANDIDAT KUAT (Hold Sementara hingga Verifikasi Manusia Selesai)**
   - Secara struktural kalimat paling utuh dan premis langsung tersampaikan.
   - Status publikasi: **Bisa dipublikasikan segera** setelah seorang editor manusia menonton dan memeriksa 3 poin checklist Klip 1 (framing wajah, kontras warna teks ASS, dan kebersihan audio di 00:18.000–00:19.486).
2. **Klip 2 (`short_02.mp4`): TERTUNDA / PERLU TINJAUAN EDITORIAL (Hold)**
   - Mengandung celah tanpa takarir sepanjang ~9,3 detik (00:09,200–00:18,500) dan filler percakapan di akhir (00:25,100–00:35,800).
   - Status publikasi: **Tidak boleh dipublikasikan langsung**. Editor manusia wajib mendengarkan celah 9,3 detik tersebut dan memutuskan apakah klip perlu dipotong manual (*jump cut*) atau digantikan kandidat lain.
3. **Klip 3 (`short_03.mp4`): TERTUNDA / PERLU PEMANGKASAN AWAL (Hold)**
   - Mengandung fragmen pengantar yang menggantung sepanjang 5 detik di awal (00:00,000–00:04,900) sebelum hook utama muncul di detik 00:05,000.
   - Status publikasi: **Perlu pemangkasan awal sebelum tayang**. Editor manusia disarankan memotong 5 detik pertama (mulai dari detik 00:05,000) agar klip memiliki daya pikat instan bagi penonton Shorts.
