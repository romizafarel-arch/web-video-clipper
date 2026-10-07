# PANDUAN BATASAN KODING & DESAIN PROYEK
## Web Video Clipper & Subtitle Studio (Reef Clipper Studio)

### I. ATURAN KODING (ENGINEERING CONSTRAINTS)
1. **Backend-Driven Video & AI Processing:** Seluruh pemotongan video, transkripsi AI (Whisper/Gemini), evaluasi viralitas (OpenAI/Gemini), dan pelacakan wajah (OpenCV) berjalan di backend Python (Flask REST API) dengan native FFmpeg, bukan WASM di browser.
2. **Proteksi Concurrency & Mutex:** Backend mengelola proses antrean/status generasi video via `JobManager` dengan proteksi pembatalan instan (`JobCancelledException`) dan batas waktu aman (`JobTimeoutException`).
3. **Single-Pass / Minimal Transcoding:** Hindari re-encoding berulang. Transcoding klip video dan rendering subtitle ASS wajib dilakukan dalam satu rantai filter FFmpeg native yang optimal tanpa perantara transcoding OpenCV berulang yang merusak kualitas video atau memicu desinkronisasi audio.
4. **Memory Safety & GPU Decoder di Frontend:**
   - Dilarang memuat elemen `<video preload="metadata">` secara massal di modal/galeri riwayat untuk mencegah crash GPU decoder (`ERR_VIDEO_DECODE_LIMIT`) dan kehabisan memori tab browser.
   - Wajib gunakan poster thumbnail statis dan lazy load decoder hanya saat kartu klip di-hover atau di-klik.
   - Selalu panggil `URL.revokeObjectURL()` jika menggunakan blob/object URL di sisi klien.
5. **Manajemen File & Persistensi:** Klip video hasil generasi disimpan di direktori output terstruktur (`output/<session_folder>/`) dengan metadata sesi (`job_<id>.json`), dan file sumber sementara dibersihkan sesuai konfigurasi.

---

### II. ATURAN DESAIN (DESIGN CONSTRAINTS)
1. **Tema Standar Video Editor:** Seluruh antarmuka menggunakan Dark Theme (`bg-zinc-950` latar utama, `bg-zinc-900` atau `bg-white/[0.03]` untuk kartu, aksen violet/cyan, border `white/10`).
2. **Layout Fleksibel & Responsif:**
   - Desktop: Workspace 2-Kolom (Kiri: Form input video & konfigurasi AI/framing; Kanan: Studio Player + Live Trimmer + Antrean Klip + Modal Riwayat Sesi).
   - Mobile: Penyesuaian responsif vertikal menggunakan `min-h-dvh` tanpa horizontal scroll.
3. **Gaya Subtitle Khas TikTok/Reels (ASS & VTT):**
   - Teks huruf tebal (font-bold, uppercase / punchy keywords).
   - Warna teks kontras tinggi (kuning terang, cyan neon, putih bersih, hijau emerald).
   - Garis tepi (Outline/Stroke) hitam pekat tebal (ASS Outline & Shadow tebal) agar selalu terbaca jelas di video apa pun.
   - Posisi subtitle fleksibel (sepertiga bawah, tengah, atau atas).
4. **Sentuhan Interaktif Real-Time:** Penyesuaian teks dan styling subtitle langsung ter-render di Studio Player secara instan sebelum dieksekusi ke backend.