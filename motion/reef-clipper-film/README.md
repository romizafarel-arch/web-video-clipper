# Reef Clipper — Cut the long. Keep the moment.

Film produk original, 20 detik, 1920×1080, 60 FPS / 1.200 frame.

## Putar

- Buka `index.html`. Klik komposisi bila browser memblokir autoplay audio.
- `Space`: jeda/lanjut. `R`: ulang. `?debug=1`: scrub waktu.
- `?clean=1`: frame awal tanpa autoplay untuk exporter.
- Semua font, GSAP, logo, dan suara tersedia di folder `assets`; tidak memerlukan internet atau instalasi untuk menonton.
- `Reef-Clipper.html` adalah salinan mandiri: aset sudah ditanam ke dalam HTML.

## Rundown

| Detik | Adegan |
|---|---|
| 00–03 | Frame original masuk dengan yaw dan roll; tipografi “Cut the long.” |
| 03–06 | Studio Player, URL YouTube fiktif, timeline, waveform, playhead, selection manual |
| 06–09 | Timeline terpisah; satu frame menjadi fokus, “Just this.” |
| 09–12 | Pilihan rasio 9:16; crop mask dan geometri frame berubah kontinu |
| 12–16 | Editor subtitle, teks manual KEEP, font Anton, tombol Simpan & Render Ulang |
| 16–18 | Triptych hasil yang sama dengan gerakan berirama |
| 18–20 | Frame terakhir menetap di samping logo asli Reef Clipper |

## Akurasi produk

Audit dibatasi ke `AGENTS.md`, `frontend/src/index.css`, Header, GeneratorForm, ClipEditorModal, API edit, dan jalur crop backend.

| Kemampuan | Bukti / batas |
|---|---|
| Masukan URL YouTube | Terhubung dari GeneratorForm ke API generate; unduhan internet tidak dijalankan dalam audit ini |
| Trim klip yang sudah ada | Diuji langsung melalui Flask `/api/edit-clip`: rentang 1–3 detik |
| Rasio 9:16 / center crop | Render nyata menghasilkan 1080×1920 |
| Subtitle manual dan burning | Cue KEEP muncul pada VTT; render actual memakai classic + Anton |
| Render MP4 dan akses output | HTTP 200, hasil berhasil didekode FFmpeg, rute output HTTP 200 |
| AI highlights / auto captions / face tracking | Tidak diuji end-to-end dan tidak diiklankan sebagai otomatis |

Film adalah rekonstruksi UI untuk motion, bukan screen recording atau benchmark. Durasi proses dipadatkan secara editorial. Timeline panjang dan pemisahan frame merupakan metafora pemilihan/trim. Montage mengulang satu hasil, bukan klaim ekspor batch.

Temuan audit: pada video uji berisi nada tanpa percakapan, cue “Keep the moment” menjadi “KEEP” pada proses penyelarasan lokal. Film menggunakan cue satu kata yang lolos pengujian. Timing tampilan caption di film adalah demonstrasi visual, bukan bukti ketepatan timing backend. Aplikasi utama tidak diperbaiki atau diubah untuk pekerjaan ini.

`product-verification.json` menyimpan hasil uji. Sumber dan scratch pengujian dihapus otomatis setelah selesai. Tidak ada panggilan layanan AI berbayar untuk audit; backend dapat menjalankan Whisper lokal untuk penyelarasan.

## Visual dan audio

- Logo: `frontend/public/favicon.svg`, dipakai utuh.
- Warna: `#0a0a0f`, `#8b5cf6`, `#22d3ee`; warna ungu muda turunan `#a78bfa` juga ada di UI repo.
- Font: Sora, Work Sans, Anton. Lisensi OFL disertakan.
- Footage: set studio dan torus original berbasis Canvas, tanpa stok, orang, atau data pribadi. Semua posisi adalah fungsi waktu timeline.
- Soundtrack: komposisi original 120 BPM, bass sintetis, click/snap dan whoosh berbasis noise ber-seed. Tidak ada rekaman pihak ketiga.
- Arsitektur: Bang Motion, satu master GSAP timeline, satu rig `#world`, directional SVG blur, `OPENER.seek(t)`. Tidak memakai Three.js.

## Ekspor ulang

Butuh Node.js, FFmpeg, Chrome, dan Playwright. Exporter memakai Playwright yang sudah terpasang di lingkungan produksi ini sebagai pengganti Puppeteer; pendekatan Bang Motion tetap sama: seek deterministik → dua frame browser → PNG → FFmpeg.

```sh
node render.mjs qc
node render.mjs preview
node render.mjs final
```

Di komputer lain, pasang Playwright bila belum ada, atau arahkan `PLAYWRIGHT_MODULE` ke module yang tersedia. `CHROME_PATH` mengatur lokasi Chrome. `render.mjs` mengalirkan PNG langsung ke encoder sehingga tidak menyimpan ribuan PNG sementara.

`make_audio.py` mereproduksi soundtrack menggunakan Python + NumPy. `verify_product.py` hanya berjalan dari checkout repo ini dengan environment Python backend lengkap.

## Kredit

Bang Motion oleh Bang Tutorial, MIT: https://github.com/bangtutorial/bang-motion

GSAP 3.12.5, GreenSock: https://gsap.com/standard-license/

Font Sora / Work Sans / Anton: Google Fonts, SIL Open Font License; salinan lisensi di `assets`.
