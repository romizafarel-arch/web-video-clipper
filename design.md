# Reef Clipper Studio Design System

## Ikhtisar (Overview)

Reef Clipper adalah sistem antarmuka studio produksi video yang dirancang untuk memotong video panjang (YouTube) menjadi klip pendek vertikal (Shorts/TikTok/Reels), menata subtitle bergaya dinamis, dan mengatur komposisi framing kamera secara presisi.

Antarmuka berfokus pada ketenangan kerja (quiet studio editor), efisiensi alur pengguna, dan hierarki visual yang jelas:
- **Alur Utama:** Tempel URL → Pilih Pengaturan Inti → Buat Klip → Tinjau/Edit Hasil di Stage Monitor.
- **Kanvas Studio Gelap:** Warna dasar gelap (#0A0A0F) memberikan kontras optimal untuk peninjauan video dan pembacaan subtitle tanpa menyilaukan mata editor.
- **Aksen Terarah:** Warna violet (#8B5CF6 / #7C3AED) digunakan khusus untuk tombol aksi utama dan indikator pilihan aktif, bukan sebagai dekorasi menyeluruh.
- **Anti-Slop:** Memangkas efek glassmorphism berlebihan, glow dekoratif, dan teks promosi bombastis. Menggunakan istilah fungsional studio dalam Bahasa Indonesia yang lugas dan jujur.

---

## Catatan Arsitektur (Architecture Note)

> [!NOTE]
> Pada dokumen historis `AGENTS.md` dan `CONSTRAINTS.md`, tercantum spesifikasi client-side WASM (@ffmpeg/ffmpeg dan IndexedDB). Namun, implementasi produksi saat ini beroperasi dengan arsitektur hybrid backend (Python FastAPI/Flask dengan yt-dlp, FFmpeg, faster-whisper, dan integrasi LLM). UI studio saat ini dirancang untuk melayani alur backend produksi tersebut secara presisi dan andal tanpa merombak mesin pemrosesan video di sisi server.

---

## Palet Warna (Color System)

- **Surface Base** (#0A0A0F): Latar belakang utama aplikasi dan stage studio.
- **Surface Card / Raised** (#12121A / zinc-900): Panel kontrol, kartu pengaturan, dan antrean klip.
- **Surface Inset** (#060609 / zinc-950): Input form, timeline track, dan wadah pratinjau monitor.
- **Border Default** (rgba(255, 255, 255, 0.08) / zinc-800): Batas pemisah komponen yang tegas dan terukur.
- **Color Primary** (#8B5CF6): Tombol aksi utama (Buat Klip), seleksi aktif, dan focus ring.
- **Color Primary Dark** (#7C3AED): Hover state tombol utama dan gradien fungsional lembut.
- **Color Secondary / Accent** (#22D3EE / cyan-400): Penanda status teknis, timecode, dan tautan sekunder.
- **Color Success** (#34D399 / emerald-400): Status pekerjaan selesai dan verifikasi konfigurasi.
- **Color Warning** (#FBBF24 / amber-400): Peringatan proses sebagian atau interupsi.
- **Color Destructive** (#F87171 / rose-400): Pembatalan tugas, kegagalan, atau penghapusan file.

---

## Tipografi (Typography)

- **Headline Font**: `Sora`, sans-serif (Judul modul studio, nama klip, angka highlight).
- **Body Font**: `Work Sans`, sans-serif (Label formulir, deskripsi, opsi pengaturan, teks antarmuka).
- **Monospace Font**: `Space Mono`, monospace (Timecode, resolusi, format aspek rasio, log pipeline).

### Skala Tipografi:
- **Title Studio**: Sora 24px-28px semibold, line-height 1.2
- **Section Heading**: Sora 16px-18px semibold, line-height 1.3
- **Control Label**: Work Sans 13px-14px medium, line-height 1.4
- **Body Text**: Work Sans 14px regular, line-height 1.5
- **Caption / Meta**: Work Sans 12px regular, line-height 1.4
- **Timecode & Data**: Space Mono 11px-13px regular, line-height 1.2

---

## Ruang & Skala (Spacing & Sizing)

Skala berbasis modul 4px / 8px:
- **space-1**: 4px (Jarak ikon inline dan badge mikro)
- **space-2**: 8px (Jarak label kontrol dan ikon)
- **space-3**: 12px-16px (Jarak internal kelompok kontrol)
- **space-4**: 16px-20px (Padding kartu dan panel studio)
- **space-5**: 24px (Pemisah modul kontrol utama)
- **space-6**: 32px (Margin antar kolom pada desktop)

---

## Radius Sudut (Border Radius)

- **radius-sm** (6px): Badge status, chip filter, tombol sekunder kecil.
- **radius-md** (10px): Tombol kontrol, input URL, kartu antrean klip.
- **radius-lg** (14px): Kartu formulir kontrol, frame monitor stage, modal dialog.
- **radius-pill** (9999px): Indikator waktu, toggle scrubber, pill badge status.

---

## Struktur Workspace Studio

### 1. Mode Desktop (2 Kolom Seimbang)
- **Kolom Kiri (Panel Kontrol Pendamping, 40%-45% lebar):**
  - Input URL video YouTube dengan tombol Tempel (Paste) cepat.
  - Pengaturan inti yang ringkas: Rasio Aspek (9:16, 1:1, 16:9), Target Jumlah Klip (1-5), Framing Kamera, Mode Engine (Lokal / Cloud API).
  - Pilihan aktif Subtitle & Font ringkas dengan tombol akses ke Galeri Lengkap.
  - Panel Lanjutan (Collapsible): Resolusi output, pemilihan model LLM & Transkripsi Audio.
  - Tombol Utama "Buat Klip Video" yang solid, kontras tinggi, dan mudah diakses.
  - Kartu Progres Pipeline jika pekerjaan sedang berlangsung.
- **Kolom Kanan (Stage Monitor & Antrean Klip Fokus, 55%-60% lebar):**
  - **Sebelum klip dibuat:** Empty state yang tenang dan jujur dengan panduan langkah studio.
  - **Setelah klip selesai:** Stage Monitor pemutar video aktif dengan overlay subtitle langsung, kontrol pemutaran, opsi posisi & warna subtitle, serta antrean klip hasil riil yang bisa dipilih, diedit, atau diunduh.

### 2. Mode Mobile (Alur Berurutan)
- Penyusunan vertikal berorientasi tugas:
  1. Header ringkas
  2. Input URL & Pengaturan Inti
  3. Tombol Utama "Buat Klip Video"
  4. Kartu Progres Job (jika aktif)
  5. Stage Monitor & Klip Hasil
- Target sentuh minimal 44x44px untuk kenyamanan jari.
- Mencegah horizontal scrollbar dan teks terpotong pada lebar 390px dan 320px.

---

## Komponen Kunci

### Tombol (Buttons)
- **Primary**: Solid background `#7C3AED` ke `#8B5CF6`, teks putih, padding tegas, hover transisi 150ms.
- **Secondary / Outline**: Border `zinc-800`, latar `zinc-900/80`, teks `zinc-200`, hover border `zinc-700`.
- **Ghost**: Tanpa border, hover background `zinc-800/50`, teks `zinc-300`.
- **Target Sentuh**: Tinggi minimal 44px untuk kontrol utama pada perangkat sentuh.

### Input Formulir
- Latar `zinc-950`, border `zinc-800`, teks `zinc-100`, placeholder `zinc-500`.
- State Focus: Border `#8B5CF6`, focus ring 2px dengan kontras minimal 3:1.

### Stage Monitor Video
- Rasio adaptif sesuai pilihan (9:16, 1:1, 16:9).
- Scrubber timeline presisi dengan label waktu `mm:ss`.
- WYSIWYG Subtitle Overlay langsung di atas video nyata.
- Tanpa animasi simulasi fiktif (tanpa rekaman palsu REC atau equalizer animasi tanpa audio riil).

### Pemilih Preset Subtitle & Font
- Di halaman utama: Ditampilkan sebagai pilihan aktif yang ringkas dan padat informasi (nama preset, font default, warna teks).
- Tombol "Buka Galeri Lengkap" membuka Dialog modal yang menyajikan seluruh 5 preset visual (Hormozi, Vox Box, Ali Abdaal, Aesthetic Cinema, MrBeast Comic) dan katalog font CapCut lengkap serta fitur upload font kustom.

---

## Aksesibilitas & Human Standard

1. **Kontras Warna**: Teks putih dan `zinc-200` pada latar `#0A0A0F` memiliki rasio kontras > 12:1 (melebihi standar WCAG AA 4.5:1). Teks sekunder `zinc-400` memiliki rasio > 5.5:1.
2. **Navigasi Keyboard**: Seluruh kontrol interaktif (input, tombol, slider, tab) dapat diakses dengan tombol `Tab`, diaktifkan dengan `Enter`/`Space`, dan modal ditutup dengan `Escape`.
3. **Indikator Fokus**: Indikator fokus yang terlihat jelas menggunakan ring violet pada semua elemen interaktif.
4. **Resilience**: Tampilan adaptif tanpa kegagalan layout di resolusi 1440px (desktop), 768px (tablet), 390px (ponsel), dan 320px (ponsel kecil).