# AI YouTube Shorts Generator - Monorepo

Struktur monorepo bersih untuk frontend (React + Vite + Tailwind + MotionKit) dan backend (Python Flask + Whisper + LLM + FFmpeg).

## 📁 Struktur Direktori

```
web-video-clipper/
├── frontend/             # React SPA (Vite + TS + Tailwind + MotionKit UI)
│   ├── src/
│   │   ├── components/   # GeneratorForm, Header, JobProgressCard, dll.
│   │   ├── lib/api.ts    # API client consume endpoint backend
│   │   └── types/        # TypeScript interfaces
│   ├── vite.config.ts    # Proxy ke http://127.0.0.1:5050 (/api & /output)
│   └── package.json
├── backend/              # Python Flask API & Shorts Generator Engine
│   ├── shorts_generator/ # Engine clipping, facecam detector, subtitles
│   ├── web_app.py        # Flask REST API server (Port 5050)
│   ├── .venv/            # Python virtualenv
│   └── requirements.txt
├── legacy/               # Arsip prototype lama (client-only ffmpeg clipper)
├── package.json          # Root workspace & script runner
└── README.md
```

## 🚀 Menjalankan Project dari Root

Pastikan dependencies terinstall di root dan frontend:
```bash
npm install
```

### 1. Jalankan Sekaligus (Frontend + Backend)
```bash
npm run dev
```

### 2. Jalankan Terpisah
- **Frontend saja** (`http://localhost:5173`):
  ```bash
  npm run dev:frontend
  ```
- **Backend saja** (`http://127.0.0.1:5050`):
  ```bash
  npm run dev:backend
  ```

### 3. Build Frontend untuk Produksi
```bash
npm run build
```
Hasil build disimpan di `frontend/dist`. Backend Flask otomatis mendeteksi folder ini jika diakses langsung tanpa dev server.
