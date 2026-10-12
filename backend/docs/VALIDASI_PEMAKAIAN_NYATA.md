# Dokumen Rencana Validasi Pemakaian Nyata (Real-World Validation Plan) — ShortsStudio

Dokumen ini memuat protokol, matriks pengujian, dan lembar evaluasi untuk memvalidasi performa serta kualitas editorial ShortsStudio pada video dunia nyata. Seluruh baseline kode Bagian A, B, dan C (commit `fb3aee9`) tetap dipertahankan tanpa perubahan kode, fitur, maupun arsitektur selama fase ini.

---

## 1. Sumber Video dan Konfigurasi Pengujian

Pengujian mencakup tiga kategori konten video dengan karakteristik yang berbeda. Setiap video ditargetkan menghasilkan 3 klip shorts berdurasi 15–60 detik.

### Matriks Konfigurasi Pengujian

| Parameter Pengujian | Video 1: Talking Head | Video 2: Podcast Dua Orang | Video 3: Video Panjang (>30 Menit) |
| :--- | :--- | :--- | :--- |
| **Kategori Konten** | Monolog / edukasi / presentasi 1 orang | Wawancara / dialog 2 orang bergantian | Ceramah / kuliah / webinar durasi panjang |
| **Target Durasi Sumber** | 5 – 10 menit | 10 – 25 menit | 40 – 60 menit (untuk uji 3 chunk) atau 31 – 35 menit (uji 2 chunk) |
| **Sumber Video (URL/File)** | *belum ditentukan* | *belum ditentukan* | *belum ditentukan* |
| **Durasi Aktual & Resolusi** | *belum ditentukan* | *belum ditentukan* | *belum ditentukan* |
| **Bahasa Audio** | *belum ditentukan* | *belum ditentukan* | *belum ditentukan* |
| **Target Jumlah Klip** | 3 klip | 3 klip | 3 klip |
| **Target Durasi per Klip** | 15 – 60 detik | 15 – 60 detik | 15 – 60 detik |
| **Provider / Model Transkripsi** | *belum ditentukan* | *belum ditentukan* | *belum ditentukan* |
| **Provider / Model Highlight** | *belum ditentukan* | *belum ditentukan* | *belum ditentukan* |
| **Mode Framing** | 9:16 (Auto-crop deteksi wajah) | 9:16 (Auto-crop deteksi wajah) | 9:16 (Auto-crop deteksi wajah) |
| **Pengaturan Subtitle** | Burned-in ASS + VTT terpisah | Burned-in ASS + VTT terpisah | Burned-in ASS + VTT terpisah |
| **Skenario Cache Uji** | Cold Run & Warm Run (file lokal tetap) | Cold Run murni | Cold Run murni |
| **Spesifikasi Perangkat Penguji**| Windows 11 / CPU / RAM / GPU (*belum ditentukan*) | Windows 11 / CPU / RAM / GPU (*belum ditentukan*) | Windows 11 / CPU / RAM / GPU (*belum ditentukan*) |
| **Batas Waktu Pekerjaan (Timeout)** | Konfigurasi default (atau *belum ditentukan*) | Konfigurasi default (atau *belum ditentukan*) | Disesuaikan dengan durasi video (*belum ditentukan*) |

*Catatan: Parameter yang berstatus "belum ditentukan" menunggu masukan sumber dan persetujuan konfigurasi sebelum eksekusi dimulai. Tidak ada sumber video fiktif atau perubahan konfigurasi aplikasi yang diterapkan secara sepihak.*

---

## 2. Ekspektasi dan Metodologi Evaluasi Framing Podcast

Mekanisme auto-crop aplikasi saat ini menggunakan Haar Cascade OpenCV yang mendeteksi wajah di setiap interval frame dan memusatkan crop pada wajah dengan bounding box terbesar (`max(faces, key=lambda f: f[2] * f[3])`). Aplikasi **belum** memiliki modul pelacak pembicara aktif berbasis analisis suara (*voice/audio-based active speaker tracking*).

### Parameter Penilaian Framing

1. **Kestabilan Crop:**
   - Perpindahan bounding box vertikal 9:16 harus stabil tanpa lonjakan mendadak (*jitter*) saat pembicara hanya melakukan gerakan mikro.
   - Evaluasi penggunaan pembobotan rata-rata posisi (*smoothing*) frame-ke-frame.
2. **Posisi Wajah & Safe Area:**
   - Wajah pembicara tidak boleh terpotong di tepi atas, bawah, kiri, atau kanan frame 9:16.
   - Penempatan wajah pada sepertiga atas frame vertikal dinilai sebagai **sasaran kualitas editorial yang dipilih (*editorial target*)**, bukan otomatis sebagai spesifikasi bug teknis.
3. **Respons Pergantian Shot:**
   - Pada shot split-screen atau bergantian, crop harus memilih salah satu wajah dengan proporsional tanpa menghasilkan pergeseran visual yang membingungkan.
4. **Keterbacaan Subtitle terhadap Framing:**
   - Kotak teks subtitle tidak boleh menimpa wajah pembicara atau terpotong oleh batasan UI pemutar vertikal YouTube Shorts di bagian bawah.

### Aturan Klasifikasi Status Framing:
- **Keterbatasan Fitur:** Kamera tetap mengarah ke wajah yang lebih dekat/besar meskipun lawan bicara yang lebih kecil sedang berbicara. Hal ini dicatat sebagai keterbatasan fungsional yang sudah diketahui, bukan bug teknis.
- **Bug Teknis:** Terjadinya distorsi aspek rasio, gambar terlipat (*tearing*), koordinat crop melompat di luar batas resolusi asli video, artefak hitam di sisi frame, atau kegagalan pembacaan frame OpenCV.

---

## 3. Cakupan dan Bukti Pemrosesan Chunk pada Video Panjang

Aplikasi membagi transkrip menjadi beberapa *chunk* jika durasi video melebihi batas video panjang (`LONG_VIDEO_THRESHOLD = 1800` detik atau 30 menit).

### Mekanisme Pembagian Chunk Aktual (`highlights.py`)
- **Ukuran Chunk (`CHUNK_SIZE_SECONDS`):** 1200 detik (20 menit).
- **Parameter Overlap (`CHUNK_OVERLAP_SECONDS`):** 60 detik.
- **Langkah Pergeseran (`step`):** $1200 - 60 = 1140$ detik.
- **Interval Aktual per Chunk:**
  - **Chunk 1:** $0$ s s.d. $\min(1200 + 60, \text{durasi}) = 0$ s s.d. $1260$ s (offset $0$ s).
  - **Chunk 2:** $1140$ s s.d. $\min(1140 + 1200 + 60, \text{durasi}) = 1140$ s s.d. $2400$ s (offset $1140$ s).
  - **Chunk 3:** Dimulai pada $1140 + 1140 = 2280$ s. Namun, iterasi loop `while start < duration` memeriksa kondisi terminasi:
    `if end >= duration: break` di mana pada Chunk 2 nilai `end = min(2340, duration)`.
    Oleh karena itu, **Chunk 3 hanya akan terbentuk jika durasi video sumber melebihi 2340 detik (39 menit)** dan memiliki segmen transkrip yang relevan pada rentang tersebut.

### Implikasi Pemilihan Durasi Sumber Video 3
1. **Jika durasi sumber 31 – 35 menit (1860 – 2100 detik):**
   - Hanya terbentuk **2 chunk** (Chunk 1 dan Chunk 2). Rentang $\ge 2280$ detik tidak ada pada video.
   - Evaluasi dibatasi pada 2 chunk yang benar-benar terbentuk. Catat Chunk 3 sebagai **"tidak berlaku"**, dan lakukan inspeksi pada bagian akhir aktual video ($1800$ s s.d. durasi akhir).
2. **Jika ingin menguji pemrosesan 3 chunk penuh:**
   - Wajib memilih video sumber dengan durasi **40 – 60 menit** (durasi $> 2340$ detik).

### Irisan Overlap dan Pembuktian Pemrosesan Chunk
- **Irisan Aktual 120 Detik:** Meskipun parameter overlap tertulis 60 detik, interval aktual Chunk 1 ($0–1260$ s) dan Chunk 2 ($1140–2400$ s) memiliki irisan sepanjang **120 detik** ($1140$ s s.d. $1260$ s).
- **Aturan Pembuktian Chunk:**
  - Kemunculan kandidat klip dengan timestamp $\ge 1140$ detik **tidak cukup** untuk membuktikan bahwa kandidat berasal dari Chunk 2, karena rentang $1140–1260$ detik juga tercakup di Chunk 1.
  - Timestamp $\ge 600$ detik juga tidak membuktikan chunk berikutnya karena masih berada di tengah Chunk 1.
  - **Bukti Sah:** Pemrosesan chunk harus dibuktikan melalui **log eksekusi per chunk** (misalnya log pipeline `[highlights] chunk 1/N...`, `[highlights] chunk 2/N...`) dan inspeksi respons LLM raw sebelum proses deduplikasi/offset merging.

### Pemisahan Bukti AI vs Pengujian Manual Editor
- **Bukti A (Seleksi AI):** Kemampuan model AI memilih dan menghasilkan highlight yang valid dari chunk lanjutan berdasarkan log per chunk.
- **Bukti B (Kemampuan Editor):** Jika AI tidak memilih kandidat dari bagian akhir aktual video, penguji wajib melakukan pengujian manual pada rentang akhir tersebut menggunakan fitur **Editor Klip** (menyetel In/Out secara manual dan menjalankan re-render). Laporan harus membedakan secara tegas antara klip hasil seleksi otomatis AI dan klip hasil manipulasi editor.

---

## 4. Pencatatan Waktu Proses, Protokol Cache, dan Penggunaan API

Pengukuran performa dan biaya dipisahkan antara proses awal (*cold run*) dan pengulangan (*warm run*).

### Protokol Pengujian Cache (Cold Run vs Warm Run)
1. **Risiko Cache Miss pada Pengulangan URL:**
   - Pengunduhan ulang URL YouTube yang sama dapat diunduh ke folder sesi baru (`output/<session_folder>/`).
   - Karena cache audio mengikat path absolut sumber (`resolved_path`), perubahan direktori sumber akan mengubah cache key dan memicu ekstraksi ulang (*cache miss*).
2. **Metodologi Pengujian Cache Sah (Warm Run):**
   - Pengujian warm run dilakukan secara terencana khusus pada **Video 1 (Talking Head)**.
   - Pengujian wajib menggunakan berkas lokal tetap dengan path absolut, ukuran file, waktu modifikasi (*mtime_ns*), dan parameter transkripsi yang identik.
   - Pemanfaatan cache dinilai berdasarkan bukti log aktual:
     - Audio hit: `[transcribe/gemini] reusing cached compressed audio: ...`
     - Transkrip hit: `[transcribe/local] transcript cache hit: ...`
   - Panggilan API pengulangan (misal jika transkrip di-cache tetapi highlight LLM dipanggil ulang) tetap dicatat dan dimasukkan ke dalam perhitungan biaya.
3. **Isolasi Lingkungan Pengujian:**
   - Pengujian cold run dijalankan pada direktori pengujian terpisah yang bersih dari cache sebelumnya guna memastikan pengukuran waktu awal yang murni tanpa kontaminasi.

### Tabel Profiling Waktu Tahapan (Latensi)

*Catatan: Seluruh nilai awal dicatat sebagai "belum terukur". Nilai aktual diisi setelah eksekusi pengujian selesai.*

| Tahap Pipeline | Metrik / Sumber Bukti | Video 1 (Cold Run) | Video 1 (Warm Run) | Video 2 (Cold Run) | Video 3 (Cold Run) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Download / Ingest Sumber** | Log `[download]` | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Ekstraksi Audio** | Log `[transcribe]` FFmpeg | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Transkripsi Audio** | Durasi request model transkrip | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Analisis Highlight** | Durasi LLM & chunking | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Face Tracking & Crop**| Durasi proses OpenCV | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Encoding Final & Subtitle**| Durasi FFmpeg render per klip | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Verifikasi Fisik Klip**| Durasi probe OpenCV/FFprobe | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Total Waktu End-to-End**| Waktu mulai hingga selesai | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |

### Matriks Penggunaan API dan Biaya

| Sesi Pengujian | Provider & Model | Jumlah Panggilan API | Input Tokens | Output Tokens | Biaya (Label: Estimasi / Aktual) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Video 1 (Cold Run)** | *belum ditentukan* | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Video 1 (Warm Run)** | *belum ditentukan* | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Video 2 (Cold Run)** | *belum ditentukan* | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |
| **Video 3 (Cold Run)** | *belum ditentukan* | *belum terukur* | *belum terukur* | *belum terukur* | *belum terukur* |

*Catatan: Seluruh pembandingan efisiensi waktu dan konsumsi token harus dilakukan pada mesin, koneksi jaringan, dan konfigurasi aplikasi yang identik.*

---

## 5. Rubrik Kualitas Editorial dan Kesiapan Publikasi

Penilaian kualitas editorial disesuaikan dengan batasan fungsional aplikasi saat ini serta memisahkan sasaran editorial dari spesifikasi teknis.

### Batasan Fungsional Editor Bawaan
- **Editor Bawaan (`web_app.py` / `app.js`):** Saat ini HANYA mendukung pengeditan judul (`title`), kalimat pembuka/hook (`hook`), batas In/Out (`start_time`, `end_time`), dan toggle subtitle.
- **Koreksi Transkrip Subtitle:** Aplikasi **belum** menyediakan antarmuka pengeditan kata per kata untuk teks subtitle transkrip di UI.
  - Koreksi judul/hook dapat diselesaikan langsung di editor bawaan.
  - Koreksi teks subtitle yang salah eja/salah dengar memerlukan editor eksternal (misal Text Editor atau Subtitle Edit pada berkas `.vtt`). Catat nama alat eksternal dan durasi pengerjaan manual yang dibutuhkan.

### Dua Format Subtitle dalam Aplikasi
1. **Subtitle Terpisah (`.vtt`):** Berkas soft subtitle berbasis web yang dimuat pada tag `<track>` video modal untuk pratinjau dan pemutaran di web.
2. **Subtitle Hardcoded (`.ass`):** Subtitle yang dibakar secara permanen (*burned-in*) ke dalam frame video MP4 oleh filter FFmpeg selama proses render.

### Kriteria Penilaian Kualitas

1. **Highlight, Hook, dan Kelengkapan Pesan:**
   - **Hook 3 Detik Pertama:** Daya tarik kalimat pembuka dalam memikat penonton.
   - **Kelengkapan Konteks:** Klip menyampaikan premis dan kesimpulan tanpa terputus secara canggung.
   - **Relevansi Virality Reason:** Kesesuaian argumen virality LLM dengan isi aktual klip.
2. **Batas Awal dan Akhir Potongan (In/Out Boundary):**
   - **In Point:** Tidak memenggal suku kata awal kalimat atau kata sambung yang canggung.
   - **Out Point:** Berhenti tepat pada akhir intonasi kalimat penutup.
   - **Durasi Fisik:** Masuk dalam rentang target Shorts (15–60 detik).
3. **Kualitas Subtitle:**
   - **Akurasi Teks:** Tingkat kebersihan dari salah dengar (*hallucination*) atau kata hilang.
   - **Sinkronisasi Waktu:** Teks muncul bersamaan dengan suara ucapan. Target $\pm 100$ ms diperlakukan sebagai **sasaran kualitas editorial yang dipilih**, bukan otomatis sebagai bug teknis.
   - **Kecepatan Baca & Kontras:** Teks nyaman dibaca dan kontras terhadap video.
4. **Framing Vertikal & Kestabilan Kamera:**
   - Wajah pembicara berada di area aman vertikal (posisi sepertiga atas adalah target kualitas editorial).
   - Transisi pergeseran crop halus tanpa efek jitter.
5. **Kualitas Media & Sinkronisasi Audio-Video:**
   - Tidak ada desinkronisasi audio-video (*A/V sync* terjaga).
   - **Komparasi Sumber Asli:** Penilaian ketajaman gambar, artefak visual, atau kejernihan suara wajib dikomparasikan dengan kualitas video sumber asli (membedakan apakah distorsi berasal dari sumber atau akibat proses render aplikasi).

### Klasifikasi Status Kesiapan Publikasi

| Status Kesiapan | Definisi Operasional | Tindakan yang Diperlukan |
| :--- | :--- | :--- |
| **Siap Dipakai** | Kualitas hook kuat, batas In/Out presisi, subtitle akurat dan sinkron, framing tepat. | Dapat langsung diunggah tanpa perubahan. |
| **Perlu Edit Ringan** | Klip menarik; hanya perlu koreksi kecil judul/hook atau geser In/Out $\le 2$ detik via editor bawaan. | Koreksi cepat melalui Editor Klip bawaan ($\le 3$ menit). |
| **Perlu Edit Besar** | Poin inti menarik tetapi perlu penyesuaian In/Out signifikan, atau koreksi teks subtitle via editor eksternal. | Perlu pemangkasan ulang rentang waktu atau edit berkas transkrip eksternal (> 3 menit). |
| **Tidak Layak Dipakai** | Klip membingungkan, pesan menggantung tanpa konteks, audio rusak dari sumber, atau framing gagal total. | Klip ditolak; tidak disarankan untuk dipublikasikan. |

---

## 6. Format Dokumentasi Temuan dan Lembar Kerja

### 1. Klasifikasi Kategori Temuan

1. **Bug Teknis:**
   - Error eksekusi, kegagalan render, exception tak tertangani, crash subprocess, desinkronisasi audio-video, berkas artefak rusak/0-byte, atau koordinat crop melompat di luar batas resolusi asli video.
2. **Masalah Kualitas Editorial:**
   - Pemilihan highlight yang kurang kuat, kalimat awal terpotong wajar, sinkronisasi subtitle melebihi $\pm 100$ ms, posisi wajah tidak ideal di sepertiga atas, atau keterbacaan teks kurang optimal.
3. **Usulan Fitur atau Performa:**
   - Usulan penambahan modul pelacak pembicara aktif berbasis suara (*voice-tracking*), editor transkrip subtitle per kata langsung di antarmuka web, opsi animasi teks, atau akselerasi hardware NVENC.

### 2. Lembar Kerja Hasil Evaluasi per Klip

| ID Klip | Kategori Video | In/Out Sumber | Durasi Fisik | Judul / Hook Kalimat | Status Kesiapan | Alat Perbaikan (Bawaan / Eksternal) | Estimasi Waktu Perbaikan | Catatan Masalah & Komparasi Sumber |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Klip-1.1` | Talking Head | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-1.2` | Talking Head | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-1.3` | Talking Head | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-2.1` | Podcast 2 Orang | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-2.2` | Podcast 2 Orang | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-2.3` | Podcast 2 Orang | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-3.1` | Video >30 Mnt | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-3.2` | Video >30 Mnt | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |
| `Klip-3.3` | Video >30 Mnt | *belum diuji* | *belum diuji* | *belum diuji* | *belum ditentukan* | - | - | *belum diuji* |

### 3. Inventaris Bukti (Evidence Log)

Setiap temuan harus didukung oleh minimal salah satu artefak bukti berikut:
- **Timestamp & Cuplikan Log:** Bukti baris log pada sesi job (`job_<id>.json` atau log worker per chunk).
- **Tangkapan Layar (Screenshot):** Bukti visual posisi framing, pemotongan teks subtitle, atau tampilan editor.
- **Berkas Video Hasil:** Path file video `.mp4` (hardcoded subtitle ASS) dan berkas `.vtt` (soft subtitle).
- **Berkas Komparasi Sumber:** Timestamp pada video sumber asli untuk verifikasi cacat bawaan vs cacat hasil render.
