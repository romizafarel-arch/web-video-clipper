# Laporan Validasi Pemakaian Nyata: Video 3 — Konten Berdurasi Panjang

**Status Akhir: PIPELINE FAILED PADA VALIDASI SEMANTIK TRANSKRIPSI (0 KLIP DIHASILKAN); KEBIJAKAN GUARD POLICY B/B & CLEANUP BERHASIL 100%.**

Pengujian validasi pemakaian nyata ShortsStudio untuk kategori **Video 3 — Konten Berdurasi Panjang (Long-Form Video, 40–45 Menit)** telah diselesaikan dalam satu eksekusi dingin (*single cold run*). Dokumen ini merekam secara objektif parameter sumber, hasil pre-flight, kronologi eksekusi, penegakan kuota/guard, investigasi akar masalah (*investigate-first*), serta kategorisasi temuan.

| Identitas Audit | Nilai Terverifikasi |
| --- | --- |
| Proyek / Tanggal | ShortsStudio / 29 September 2026 (WIB, UTC+07:00) |
| Repositori Aktif | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator` |
| Branch / Baseline HEAD | `main` / `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e` (tanpa perubahan kode produksi) |
| Dokumen Acuan | [RENCANA_VALIDASI_VIDEO_3_PANJANG.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/RENCANA_VALIDASI_VIDEO_3_PANJANG.md), [REVIEW_RUNNER_VIDEO_3_FINAL.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_RUNNER_VIDEO_3_FINAL.md), [VALIDASI_PEMAKAIAN_NYATA.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/VALIDASI_PEMAKAIAN_NYATA.md) |
| Runner Harness | `scratch/run_validation_v3.py` (SHA-256: `3b5e4eef614327a7216bfb72a8cd212541b4bf18b830f75b42c8b3e0a6a306b1`) |
| Direktori Output & Cache V3 | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v3\` |
| Preservasi Media/Cache V1 & V2 | Terverifikasi utuh, tidak disentuh, checksum identik dengan laporan terdahulu |

---

## 1. Spesifikasi Media Sumber Terverifikasi

Sumber media diperoleh dari video YouTube bertema psikologi dan percakapan mendalam berbahasa Indonesia dengan durasi aktual 43 menit 50,66 detik (memenuhi kriteria perencanaan 40–45 menit dan kontinuitas percakapan melampaui detik ke-2280):

| Atribut Sumber | Nilai Terverifikasi |
| --- | --- |
| Judul Konten Asli | Trauma dan Bekasnya: Ketika Masa Lalu Menghantui Masa Sekarang \| PAB #50 Psikolog Koleta Acintya |
| Channel / Penerbit | Bicarakan ID |
| URL Resmi YouTube | `https://www.youtube.com/watch?v=A72GOa6M5fY` |
| Jalur Berkas Fisik Lokal | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v3\source_long_v3.mp4` |
| Ukuran Berkas (`size_bytes`) | 112.410.774 byte (~107,20 MB) |
| Hash SHA-256 Berkas | `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` |
| Durasi Fisik Sumber | 2.630,66 detik (43 menit 50,66 detik) |
| Format Video / Audio | H.264 (Main) 1280x720 @ 29.97 fps (SAR 1:1, DAR 16:9) \| AAC stereo 44.100 Hz, 128 kbps |
| Kontinuitas Ucapan >2280s | Terverifikasi aktif (`mean_volume: -24.5 dB`, `max_volume: -3.8 dB` pada rentang detik 2280–2480) |
| Uji Decode Bitstream | FFmpeg `-xerror` pada detik 10, 1200, 2350: exit code 0, stderr kosong |
| Uji Baca Frame OpenCV | `cv2.VideoCapture` pada detik 10 (frame 299), 1200 (frame 35964), 2350 (frame 70429): `ret=True`, shape `(720, 1280, 3)` |

---

## 2. Pemeriksaan Pra-eksekusi (Pre-flight Check)

Sebelum eksekusi dingin dijalankan, pre-flight check dieksekusi secara independen dari `.venv` aktif dan disimpan di `output_val_v3/preflight_v3_check.json`:
- **Isolasi Output**: `LOCAL_OUTPUT_DIR` terikat mutlak ke `output_val_v3` pada modul config, transcriber, gemini_transcriber, dan web_app.
- **Cache Terisolasi**: Audio cache di `output_val_v3/.cache/audio/`, transkrip cache di `output_val_v3/.cache/transcripts/`.
- **Preservasi Artefak Lama**: Seluruh cache dan artefak Video 1 (`output_val_v1/`) dan Video 2 (`output_val_v2/`) terverifikasi utuh.
- **Policy B/B Terpasang**: `max_retries = 0` pada OpenAI client, `MAX_HIGHLIGHT_API_ATTEMPTS = 1`, kuota transkripsi maks 1, kuota highlight maks 4, fallback multimodal diblokir ketat.

---

## 3. Rekapitulasi Eksekusi Cold Run Video 3

| Parameter | Hasil Eksekusi Cold Run (`val_v3_long_72842`) |
| --- | --- |
| Job ID | `val_v3_long_72842` |
| Session Folder | `20260929_160722_val_v3_long_72842` |
| Process ID (PID) | 13812 |
| Waktu Mulai (ISO) | `2026-09-29T16:07:22.321749+07:00` |
| Waktu Selesai (ISO) | `2026-09-29T16:09:22.167429+07:00` |
| Durasi Wall-Clock Runner | 119,85 detik |
| Durasi Metadata Disk | 119,81 detik |
| Status Akhir (In-Memory & Disk) | `failed` / Stage: `failed` |
| Worker Thread Status | Berhenti bersih (`worker_thread_alive: false`) |
| Pengelolaan Siklus Hidup | `job_manager.get_active_job()`: `None`, `web_app.get_active_job()`: `None` |
| Pesan Kegagalan Utama | `Transkripsi model fallback (gemini-3.5-flash) diblokir oleh kebijakan harness Video 3 (Policy B/B: fail-fast pada gemini-3.5-transcribe, dilarang fallback ke model lain).` |
| Ekstraksi Audio Lokal | Berhasil: `audio_source_long_v3_204cf641966b862d.mp3` (20,07 MB / 21.046.368 byte, 16kHz mono) |
| Staging File API | Upload berhasil ke `files/e695ayr7f94n` (durasi ~10,4 detik) |
| Penghapusan Staging File API | Berhasil dihapus (`files/e695ayr7f94n`, status: `delete_success: 1`) |
| Klip Shorts MP4 Dihasilkan | 0 (pipeline terhenti pada tahap transkripsi sebelum pemeringkatan highlight) |

### Audit Trail Penggunaan API (Policy B/B Counters)

```json
{
  "transcribe": {
    "attempted": 1,
    "dispatched": 1,
    "success": 1,
    "failed": 0,
    "blocked": 1,
    "max": 1
  },
  "highlight": {
    "attempted": 0,
    "dispatched": 0,
    "success": 0,
    "failed": 0,
    "blocked": 0,
    "max": 4
  },
  "file_api": {
    "upload": 1,
    "polling": 0,
    "delete": 1,
    "delete_success": 1,
    "delete_failed": 0
  }
}
```

*Catatan Biaya*: Biaya finansial aktual dicatat sebagai **"Belum terukur"** karena ketiadaan rincian penagihan (*billing invoice*) API resmi seketika.

---

## 4. Investigasi Mendalam Kegagalan Transkripsi (*Investigate-First*)

### 4.1 Kronologi dan Mekanisme Kegagalan
1. Audio 20,07 MB dikirim ke model spesialis ucapan Google `gemini-3.5-transcribe` via Gemini File API dengan parameter `word_timestamp=True, language_codes=['id']`.
2. Model mengembalikan respons transkripsi yang memuat **5.851 kata mentah** (*raw words*) dalam waktu ~91 detik.
3. Fungsi produksi `_words_to_segments` pada `shorts_generator/local/gemini_transcriber.py` melakukan validasi per-kata:
   ```python
   # shorts_generator/local/gemini_transcriber.py:365-369
   if end_t < start_t:
       raise ValueError(
           f"[transcribe/gemini] Word {idx} ({word_text!r}) has inverted time range: "
           f"end_offset ({end_t}) < start_offset ({start_t})."
       )
   ```
4. Pada kata ke-1228 (`'hyper'`), model Google mengembalikan:
   `start_offset = '516.300s'`, `end_offset = '514.600s'`.
   Karena `end_t (514.6) < start_t (516.3)`, fungsi melempar `ValueError`.
5. Kode produksi menangkap `ValueError` ini sebagai kegagalan `gemini-3.5-transcribe` dan secara otomatis berusaha melakukan *fallback* ke model multimodal (`gemini-3.5-flash`).
6. Sesuai kebijakan **Policy B/B** yang telah disahkan, runner mengintersepsi pemanggilan fallback ini dan menghentikannya (*fail-fast*), mencatat `blocked: 1` pada counter transkripsi.
7. Modul `finally` pada transcriber berhasil melakukan *cleanup* remote File API (`client.files.delete(name='files/e695ayr7f94n')`) tanpa menyisakan berkas yatim di Google Cloud Storage.
8. Berkas diagnostik pre-validation berhasil disimpan secara utuh:
   `output_val_v3/20260929_160722_val_v3_long_72842/diagnostic_transcript_pre_validation_val_v3_long_72842.json` (751.150 byte).

### 4.2 Analisis Anomali Timestamp pada Respons Model Upstream
Pemeriksaan menyeluruh terhadap seluruh 5.851 kata pada berkas diagnostik membuktikan adanya anomali sistemik dari model `gemini-3.5-transcribe` pada pemrosesan audio berdurasi panjang:

1. **Kata dengan Rentang Waktu Terbalik (`end_offset < start_offset`)**:
   Ditemukan **28 kata** dengan timestamp terbalik. Contoh signifikan:
   - Kata 1228: `'hyper'` (start: 516,3s, end: 514,6s)
   - Kata 1230: `'hyper'` (start: 516,3s, end: 514,6s)
   - Kata 2520: `'jadi'` (start: 12010,1s, end: 120,3s) — *start offset halusinasi melompat ke 12.010 detik padahal durasi video hanya 2.630 detik!*
   - Kata 4611: `'Tapi'` (start: 2009,8s, end: 1010,1s)
   - Kata 4661: `'kita'` (start: 3030,2s, end: 2030,4s)
   - Kata 5429: `'mengembalikan'` (start: 2419,8s, end: 0,2s)
2. **Duplikasi / Stutter Halusinasi pada Indeks 1228–1231**:
   ```
   Word 1227: 'em'      (start: 512.5s, end: 512.6s)
   Word 1228: 'hyper'   (start: 516.3s, end: 514.6s)  <-- INVERTED
   Word 1229: 'arousal' (start: 514.6s, end: 515.2s)
   Word 1230: 'hyper'   (start: 516.3s, end: 514.6s)  <-- INVERTED & DUPLICATE
   Word 1231: 'arousal' (start: 514.6s, end: 515.2s)
   ```
3. **Lompatan Waktu Non-Monotonik (*Backward Start Jumps*)**:
   Ditemukan **36 titik** di mana `start_offset` melompat mundur dibandingkan kata sebelumnya (misal kata 131 `'Gimana'` pada 60,3s setelah kata sebelumnya pada 62,4s; kata 717 `'Yes'` pada 300,0s setelah 301,3s).

---

## 5. Kategorisasi Temuan

Berdasarkan fakta empiris yang diperoleh dari run dingin ini:

### 5.1 Bug Teknis & Kesenjangan Ketahanan (Technical Bug / Robustness Gap — P1)
- **Komponen Terdampak**: `shorts_generator/local/gemini_transcriber.py` baris 365–369.
- **Deskripsi Masalah**: Penolakan kaku (*hard rejection*) terhadap kesalahan timestamp kata upstream. Pada audio panjang (>30–40 menit), model transkripsi AI sering mengalami lonjakan kecil (*jitter*) atau halusinasi offset pada frasa berulang. Membatalkan seluruh transkripsi 44 menit (5.851 kata) dan menggagalkan job hanya karena 1 kata mengalami pembalikan offset merupakan desain yang terlalu rapuh (*brittle*) untuk penggunaan dunia nyata.
- **Rekomendasi Solusi Teknis (Untuk Tahap Berikutnya)**:
  Tambahkan lapisan **Heuristic Timestamp Sanitizer**:
  1. Jika `end_offset < start_offset`, tukar nilainya jika keduanya masuk akal, atau tetapkan `end_offset = max(start_offset, prev_end + 0.05)`.
  2. Jika `start_offset` melompat liar melampaui durasi fisik media (seperti kasus kata 2520 pada 12.010 detik), interpolasikan offset dari kata tetangga atau abaikan timestamp kata tersebut tanpa membuang teksnya.
  3. Lakukan sanitasi ini sebelum proses segmentasi agar pipeline tetap dapat melanjutkan ke tahap highlight.

### 5.2 Kualitas Editorial (Editorial Quality)
- **Status Evaluasi**: **Belum dinilai (Not Evaluated)**.
- **Keterangan**: Pipeline berhenti pada tahap transkripsi sehingga tidak ada klip shorts yang dipotong atau dirender. Evaluasi framing wajah 9:16, keterbacaan ASS subtitle, dan kohesi narasi hook ditangguhkan sampai transkrip berhasil diproses.

### 5.3 Status Kesiapan Publikasi
| Klip | File MP4 | Subtitle WebVTT | Kesiapan Publikasi | Status Verifikasi Audio |
| :---: | :---: | :---: | :---: | :---: |
| **Klip 1** | Tidak ada | Tidak ada | **Belum tersedia (pipeline gagal)** | Belum diperiksa audio |
| **Klip 2** | Tidak ada | Tidak ada | **Belum tersedia (pipeline gagal)** | Belum diperiksa audio |
| **Klip 3** | Tidak ada | Tidak ada | **Belum tersedia (pipeline gagal)** | Belum diperiksa audio |

### 5.4 Proposal Fitur & Peningkatan Arsitektur (Feature Proposals)
1. **Lapisan Perbaikan Timestamp Heuristik Transkripsi**: Menyematkan modul pembersih anomali timestamp pada seluruh provider transkripsi agar kebal terhadap *glitch* model AI upstream.
2. **Strategi Fallback Transkripsi Lokal Bertingkat**: Jika transkrip cloud (Gemini) gagal secara fatal, pertimbangkan fallback ke transcriber lokal berbasis GPU/CPU (Whisper) sebelum mencoba fallback multimodal LLM yang memakan kuota token besar.
3. **Chunking Audio pada Fase Transkripsi**: Untuk media berdurasi sangat panjang (>30 menit), pertimbangkan memecah audio menjadi berkas 15–20 menit sebelum dikirim ke STT API guna meminimalkan halusinasi akumulatif pada model speech-to-text.

---

## 6. Inventaris Bukti Audit (*Audit Trail Evidence*)

Semua artefak validasi Video 3 tersimpan di direktori repositori:

| Berkas Artefak | Lokasi / Path | Keterangan |
| --- | --- | --- |
| Sumber Video 3 | `output_val_v3/source_long_v3.mp4` | 112.410.774 byte, SHA-256: `d4e1d8bc...` |
| Ekstraksi Audio Cache | `output_val_v3/.cache/audio/audio_source_long_v3_204cf641966b862d.mp3` | 21.046.368 byte (20,07 MB) |
| Laporan Pre-flight | `output_val_v3/preflight_v3_check.json` | Status: PASSED |
| Metadata Pekerjaan Disk | `output_val_v3/20260929_160722_val_v3_long_72842/job_val_v3_long_72842.json` | Status: `failed`, durasi: 119,81s |
| Bukti Diagnostik Transkrip | `output_val_v3/20260929_160722_val_v3_long_72842/diagnostic_transcript_pre_validation_val_v3_long_72842.json` | 751.150 byte, 5.851 kata mentah |
| Ringkasan Verifikasi Runner | `output_val_v3/validation_v3_summary_val_v3_long_72842.json` | Ringkasan terperinci per-job |
| Ringkasan Pointer Verifikasi | `output_val_v3/validation_v3_verification_summary.json` | Ringkasan identik untuk pointer evaluasi |

---

## 7. Kesimpulan dan Rekomendasi Selanjutnya

1. **Integritas Guard dan Runner**: Runner harness Video 3 bekerja sesuai spesifikasi: penegakan kuota ketat (maks 1 transkripsi, 0 fallback LLM), isolasi direktori berjalan sempurna, dan File API staging berhasil dihapus seketika setelah job gagal.
2. **Preservasi**: Seluruh aset Video 1 dan Video 2 tetap 100% aman dan identik.
3. **Langkah Penutupan**: Kegagalan cold run Video 3 telah terpetakan secara tuntas ke akar masalah konkret (`gemini-3.5-transcribe` timestamp anomalies vs strict assertion di `gemini_transcriber.py`). Tidak ada retry liar yang dilakukan. Tahap selanjutnya adalah menyusun usulan perbaikan teknis (*patching*) pada modul transcriber sebelum pengujian berikutnya dapat diizinkan.
