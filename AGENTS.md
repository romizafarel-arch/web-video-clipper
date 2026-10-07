# ATURAN SISTEM UNTUK PROYEK VIDEO CLIPPER (REEF CLIPPER STUDIO)

- Framework Frontend: React 19+ (Vite) + TypeScript + Tailwind CSS.
- Framework Backend: Python 3.10+ (Flask REST API + native FFmpeg + AI pipelines).
- Arsitektur: Client-Server Hybrid Architecture. Backend Python menangani beban berat: unduhan video (yt-dlp), transkripsi audio (Whisper/Gemini), penentuan highlight viral (OpenAI/Gemini), pelacakan wajah & framing (OpenCV), serta transcoding video & subtitle burning (native FFmpeg). Frontend React mengelola Studio Player, kustomisasi subtitle, trimmer editor, riwayat sesi, dan pemantauan job secara real-time via REST API.
- TypeScript: Jangan pernah menggunakan 'any'. Gunakan interface strict (AppConfig, HistorySession, HistoryShort, EditableClip, VideoClip).
- Memory Safety & GPU Decoder:
  - Frontend: Hindari inisialisasi elemen `<video>` massal di modal riwayat; gunakan poster thumbnail statis dan lazy load decoder saat kartu klip di-hover atau di-klik. Revoke Object URLs jika menggunakan file lokal.
  - Backend: Hapus file video sumber dan file scratch sementara setelah proses selesai atau ketika job dibatalkan/timeout.
- Subtitle Styling: Gunakan font tebal dengan outline/stroke hitam tebal (TikTok/Reels style) melalui styling ASS (Advanced SubStation Alpha) dan VTT.
- Styling UI: Wajib Dark Theme (Zinc/Slate palette), responsif mobile (min-h-dvh) dan desktop 2-kolom.