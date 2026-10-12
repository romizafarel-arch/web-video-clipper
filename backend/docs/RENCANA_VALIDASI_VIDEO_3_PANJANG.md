# Dokumen Perencanaan Validasi Pemakaian Nyata: Video 3 — Konten Berdurasi Panjang

**Status Dokumen: DRAFT PERENCANAAN TEKNIS (BELUM DIEKSEKUSI).**

Dokumen ini memuat rencana pengujian dan batasan operasional untuk validasi pemakaian nyata kategori **Video 3 — Konten Berdurasi Panjang (Long-Form Video)** pada ShortsStudio, mengacu pada [VALIDASI_PEMAKAIAN_NYATA.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/VALIDASI_PEMAKAIAN_NYATA.md), rekomendasi [REVIEW_VIDEO_2_SIGNOFF_DAN_RENCANA_VIDEO_3.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_VIDEO_2_SIGNOFF_DAN_RENCANA_VIDEO_3.md), serta arahan perbaikan [REVIEW_PERSIAPAN_VIDEO_3.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_PERSIAPAN_VIDEO_3.md).

> [!IMPORTANT]
> **Pemberitahuan Batas Eksekusi**: Dokumen ini hanya merupakan rancangan teknis persiapan. **TIDAK ADA PANGGILAN API, TRANSKRIPSI, ATAU EKSEKUSI PIPELINE YANG DILAKUKAN** dalam tahap ini. Seluruh parameter sumber, kuota, dan izin penggunaan API bertanda **"Belum ditentukan"** sampai disetujui secara eksplisit oleh pengguna.

---

## 1. Sasaran dan Kriteria Keberhasilan Video 3

Tujuan utama validasi Video 3 adalah menguji stabilitas, skalabilitas, dan integritas pipeline ShortsStudio terhadap media berdurasi panjang:
1. **Verifikasi Pemecahan Tiga Chunk (Chunking Mechanism)**: Membuktikan bahwa transkrip video berdurasi 40–45 menit dipartisi secara deterministik menjadi **tepat 3 chunk** (jika segmen ucapan tersebar di ketiga rentang) dengan dua zona overlap yang benar oleh fungsi `chunk_transcript`:
   - Overlap pertama: detik **1140–1260** (pertemuan Chunk 1 dan Chunk 2).
   - Overlap kedua: detik **2280–2400** (pertemuan Chunk 2 dan Chunk 3).
2. **Pembedaan Konseptual Chunk vs Klip**: Jumlah chunk pemrosesan (3 chunk) tidak disamakan dengan jumlah target klip akhir (3 klip shorts). Tiga klip shorts adalah **target keluaran yang diharapkan, bukan jaminan ketersediaan kandidat valid atau keberhasilan render**. Klip terbaik dipilih dari seluruh kandidat lintas chunk setelah rekonsiliasi offset dan deduplikasi lokal berbasis skor.
3. **Kepatuhan Guard Kebijakan B/B**:
   - Penegakan batas inferensi fail-fast: maksimal 1 transkripsi Gemini dan maksimal 4 highlight APMix.
   - Penolakan absolut terhadap fallback transkripsi multimodal (`gemini-3.5-flash`).
   - Penegakan `max_retries = 0` pada SDK OpenAI serta harness override `MAX_HIGHLIGHT_API_ATTEMPTS = 1` pada tingkat aplikasi untuk menghentikan loop retry tersembunyi saat respons ranking kosong atau invalid.
   - Pencatatan operasi File API (upload, polling via `Files.get`, dan status delete success/failed) secara terpisah dari model inference.
4. **Manajemen Batas Waktu & Request (V3-01)**:
   - Batas waktu job 1.800 detik dikelola secara **kooperatif** (belum menjamin penghentian keras tepat pada detik 1800).
   - Cadangan waktu 60 detik ditetapkan sebagai **parameter perencanaan** (belum dibuktikan secara fisik kecukupannya untuk render/cleanup).
   - Anggaran request inferensi dihitung dinamis dari sisa deadline dikurangi cadangan, dan dipasangkan ke timeout jaringan SDK (OpenAI dalam detik, Gemini `HttpOptions.timeout` dalam milidetik).
   - Pemeriksaan cancel/deadline dieksekusi sebelum request, sesudah respons diterima, dan saat exception terjadi.
5. **Pemetaan Hasil Parsial yang Andal (V3-02)**:
   - Pencocokan berkas MP4 dengan completion record berdasarkan `clip_index` atau nama berkas kanonikal, bukan urutan list.
   - Menjamin akurasi metadata ketika klip parsial hilang (misal #1 gagal, #2 dan #3 selesai), urutan list diacak, atau berkas tanpa completion record ditemukan.
6. **Integritas Media Akhir**: Seluruh klip shorts MP4 vertikal 9:16 dan berkas WebVTT lolos decode penuh FFmpeg (`-xerror`, exit 0, stderr kosong).

---

## 2. Parameter dan Sumber Media Terencana

| Parameter | Spesifikasi Rencana | Status Persetujuan / Nilai |
| --- | --- | :---: |
| **Kategori Konten** | Video narasi panjang / seminar / talkshow / podcast panjang | Belum ditentukan |
| **Durasi Target Sumber** | **40–45 menit** (rentang optimal untuk menghasilkan maksimal 3 chunk tanpa memicu chunk ke-4, diharapkan 3 chunk jika transkrip mencakup ketiga rentang) | Belum ditentukan |
| **Kandidat URL YouTube** | Talkshow/Podcast Bahasa Indonesia stabil (misal Endgame Gita Wirjawan / Catatan Najwa / Diskusi Kebijakan Publik) | Belum ditentukan |
| **Bahasa Konten** | Bahasa Indonesia (`id`) | Belum ditentukan |
| **Kontinuitas Ucapan Akhir** | Ucapan pembicara berlanjut melampaui detik ke-2280 (38 menit) hingga akhir | Belum ditentukan |
| **Jalur Berkas Lokal Sumber** | `output_val_v3/source_long_v3.mp4` | Belum tersedia (belum diunduh) |
| **Ukuran Berkas (`size_bytes`)** | Estimasi 250–500 MB (belum diunduh) | Belum tersedia |
| **Resolusi & Codec Sumber** | Target 720p/1080p, H.264 / AAC | Belum tersedia |
| **Waktu Modifikasi (`mtime`)** | Timestamp berkas lokal saat disimpan | Belum tersedia |
| **Hash SHA-256 Sumber** | Hash SHA-256 berkas fisik lokal | Belum tersedia |

*Catatan Karakteristik Chunk*: Berdasarkan aturan produksi `chunk_transcript` (panjang chunk 1260 detik, step 1140 detik):
- Tiga chunk **diharapkan apabila transkrip mencakup ketiga rentang durasi** (0–1260s, 1140–2400s, 2280s–akhir). Jumlah aktual harus dibuktikan melalui log eksekusi nyata karena chunk tanpa segmen ucapan akan dilewati oleh pipeline.
- Rentang durasi 40–45 menit membatasi jumlah chunk maksimal 3 pada konfigurasi saat ini, tetapi simulasi fixture belum menjamin konten transkrip nyata.
- Durasi 35 menit: menghasilkan 2 chunk (3 request highlight).
- Durasi 40–45 menit: menghasilkan maksimal 3 chunk (4 request highlight nominal).
- Durasi >58 menit: menghasilkan $\ge 4$ chunk.

---

## 3. Isolasi Lingkungan, Output, dan Preservasi Artefak

Isolasi mutlak ditegakkan sebelum modul aplikasi diimpor:
- `LOCAL_OUTPUT_DIR = "output_val_v3"`
- Direktori output: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v3\`
- Direktori cache audio: `output_val_v3\.cache\audio\`
- Direktori cache transkrip: `output_val_v3\.cache\transcripts\`
- **Preservasi Artefak Terdahulu**: Direktori `output_val_v1\` dan `output_val_v2\` serta seluruh cache dan diagnostiknya diproteksi penuh dan tidak disentuh sedikit pun (terverifikasi SHA-256).

---

## 4. Rencana Kebutuhan API & Batasan Guard (Policy B/B)

Kebutuhan nominal inferensi untuk memproses video 3-chunk dirancang sebagai berikut:

| Komponen API | Model Terencana | Peran & Frekuensi | Kebutuhan Nominal | Status Batas Pengeluaran |
| --- | --- | --- | :---: | :---: |
| **Gemini Transcribe** | `gemini-3.5-transcribe` | Transkripsi audio lengkap sumber via File API | Tepat 1 inferensi | **Belum ditentukan** |
| **Gemini Fallback** | `gemini-3.5-flash` | Multimodal prompt fallback | **0 (Dilarang keras)** | Ditegakkan guard |
| **APMix Klasifikasi** | `deepseek-v4-flash-free` | Deteksi kategori konten dan densitas | 1 inferensi | **Belum ditentukan** |
| **APMix Ranking Chunk 1** | `deepseek-v4-flash-free` | Pemeringkatan kandidat Chunk 1 (0s–1260s) | 1 inferensi | **Belum ditentukan** |
| **APMix Ranking Chunk 2** | `deepseek-v4-flash-free` | Pemeringkatan kandidat Chunk 2 (1140s–2400s) | 1 inferensi | **Belum ditentukan** |
| **APMix Ranking Chunk 3** | `deepseek-v4-flash-free` | Pemeringkatan kandidat Chunk 3 (2280s–akhir) | 1 inferensi | **Belum ditentukan** |
| **Total Highlight LLM** | - | 1 klasifikasi + 3 ranking chunk | **4 inferensi** | **Belum ditentukan** |

> [!WARNING]
> Batas 2 highlight pada Video 2 TIDAK DAPAT disalin ke Video 3 karena struktur video panjang 3-chunk secara nominal membutuhkan 4 request (1 deteksi densitas + 3 pemeringkatan per-chunk). Angka 4 request di atas adalah **kebutuhan rencana teknis**, BUKAN izin pengeluaran API otomatis. Eksekusi memerlukan persetujuan eksplisit batas kuota dari pengguna.

### Kebijakan Penegakan Guard
1. **Koneksi SDK OpenAI**: `max_retries = 0` terkunci pada klien runner.
2. **Override Percobaan Aplikasi**: Nilai `shorts_generator.highlights.MAX_HIGHLIGHT_API_ATTEMPTS = 1` ditetapkan pada proses harness agar respons ranking berupa JSON kosong atau tidak valid langsung menghentikan job secara *fail-fast* tanpa retry tersembunyi.
3. **Penyelamatan File API**: Operasi `Files.upload`, `Files.get` (polling), dan `Files.delete` dibatasi timeout terbatas. Penghapusan berkas staging Gemini File API tetap diupayakan pada blok `finally` atau saat penghentian jalur ketika ID berkas sudah diketahui (hasil dicatat pada api_counters, bukan jaminan pembersihan tanpa syarat jika jaringan gagal sebelum ID diperoleh).
4. **Penerusan Exception Kontrol**: Sinyal pembatalan (`JobCancelledException`) dan batas waktu (`JobTimeoutException`) pada pemeriksaan checkpoint diteruskan secara langsung tanpa diubah menjadi error generik atau fallback.

---

## 5. Instrumentasi Profiling & Manajemen Batas Waktu (Timeout)

### 5.1 Analisis Batas Waktu (Timeout) 1.800 Detik dan Asumsi Latensi
- Pada Video 2 (sumber 8 menit), 1 pemanggilan ranking highlight memakan waktu 268,17 detik.
- *Estimasi Kapasitas Teoritis (Asumsi Perencanaan, Belum Terukur)*:
  - Transkripsi audio panjang: diasumsikan $\approx 60\text{--}120$ detik (*asumsi perencanaan*).
  - 3 pemanggilan ranking highlight: kapasitas teoritis $\approx 800$ detik (*asumsi kapasitas, belum terukur*).
  - Rendering 3 klip shorts: diasumsikan $\approx 250\text{--}350$ detik (*asumsi perencanaan*).
  - Total waktu pipeline: diasumsikan berada di kisaran $1.100\text{--}1.300$ detik (*asumsi skenario, belum terukur*).
- **Sifat Batas Waktu 1.800 Detik**: Batas 1.800 detik saat ini bersifat **kooperatif** melalui `JobContext` dan per-request SDK timeout; mekanisme ini **belum menjamin penghentian keras (*hard kill*) tepat pada detik 1.800** jika proses/thread masih tertahan.
- **Cadangan 60 Detik**: Cadangan waktu 60 detik ditetapkan sebagai **parameter perencanaan**; kecukupannya untuk fase rendering dan cleanup belum dibuktikan secara fisik dan wajib dievaluasi pada run nyata.

### 5.2 Metrik Profiling yang Dicatat
1. Waktu ekstraksi dan verifikasi integritas audio lokal.
2. Waktu upload Gemini File API dan latensi transkripsi.
3. Latensi inferensi highlight terpisah:
   - Klasifikasi densitas.
   - Ranking Chunk 1.
   - Ranking Chunk 2.
   - Ranking Chunk 3.
4. Latensi rendering per klip (face-tracking crop, OpenCV, subtitle burning, encoding H.264/AAC).
5. Pengukuran *Peak Memory (RAM)*: Saat ini diberi label **Belum terukur** karena belum diinstrumentasikan secara fisik.
6. Total durasi *wall-clock* runner dan metadata disk.

---

## 6. Protokol Audit Trail & Penyimpanan Bukti

1. **Summary per Job ID**: Runner akan menyimpan ringkasan resmi ke `output_val_v3/validation_v3_summary_{job_id}.json` secara permanen, selain pointer ringkasan terbaru `validation_v3_verification_summary.json`.
2. **Penyimpanan Kandidat Relatif per Chunk**: Berkas `raw_candidates_chunk_req_{n}.json` menyimpan kandidat tervalidasi setelah parsing dan sanitasi schema dari `call_highlight_api`, sebelum penyesuaian offset waktu global dan sebelum deduplikasi. Berkas ini **bukan respons LLM mentah** dan tidak menyimpan respons ranking invalid yang gagal sebelum fungsi kembali.
3. **Pemeriksaan Titik Kritis Sumber**:
   - Bagian awal video: detik **0–120**.
   - Zona overlap pertama (Chunk 1 & 2): detik **1140–1260**.
   - Inti Chunk 2: detik **1260–2280**.
   - Zona overlap kedua (Chunk 2 & 3): detik **2280–2400**.
   - **Zona akhir dinamis**: 2 menit terakhir durasi aktual sumber (misal `durasi_aktual - 120s` hingga `durasi_aktual`), bukan batas kaku `>2400s`.
   - *Catatan Seleksi*: Jika model AI tidak memilih kandidat dari bagian akhir video, pengujian editorial manual dilakukan pada segmen media yang ada tanpa memicu inferensi AI tambahan.

---

## 7. Rubrik Penilaian Editorial dan Kesiapan Publikasi

Penilaian klip hasil Video 3 akan menerapkan metode yang jujur dan terukur:
1. **Metode Pemeriksaan**: Membedakan secara eksplisit antara inspeksi frame statis, verifikasi bitstream FFprobe/decode, analisis teks transkrip/VTT, dan pemutaran audiovisual manual.
2. **Empat Kategori Kesiapan Publikasi Awal**:
   - **Siap Dipakai**: Kualitas hook kuat, batas In/Out presisi, subtitle akurat dan sinkron, framing tepat.
   - **Perlu Edit Ringan**: Klip menarik; hanya perlu koreksi kecil judul/hook atau pergeseran batas In/Out $\le 2$ detik via editor bawaan.
   - **Perlu Edit Besar**: Poin inti menarik tetapi memerlukan pemangkasan ulang rentang waktu signifikan, atau perbaikan teks transkrip subtitle via editor eksternal.
   - **Tidak Layak**: Klip membingungkan, pesan menggantung tanpa konteks, audio rusak dari sumber asli, atau framing gagal total.
3. **Status Verifikasi Audio (Terpisah)**:
   - Status pemutaran audio dipisahkan sebagai atribut verifikasi: *Lolos Pemutaran Audiovisual Penuh* vs *Belum Diperiksa Audio*. Status ini mandiri dan tidak mereduksi atau menggantikan 4 kategori kesiapan publikasi di atas.
4. **Estimasi Waktu Perbaikan**:
   - Waktu perbaikan manual yang belum diukur secara riil tidak boleh diisi dengan angka rekaan; wajib diberi label *asumsi* atau dicatat setelah pengerjaan nyata selesai.
