# Dokumen Validasi Pemakaian Nyata: Video 2 — Podcast Dua Pembicara

**Status Akhir: PIPELINE & INTEGRITAS MEDIA: PASS; KUALITAS EDITORIAL: PERLU PENYESUAIAN (BELUM PASS PENUH).**

Pengujian validasi pemakaian nyata ShortsStudio untuk kategori **Video 2 — Podcast dengan Dua Pembicara** telah diselesaikan sebagai pengujian teknis. Dokumen ini merekam secara objektif seluruh siklus pengujian, pembuktian kegagalan, koreksi teknis, evaluasi media, dan inventaris bukti audit:
1. **Cold Run Pertama (`val_v2_pod_37266`)**: Gagal pada validasi kontrak transkrip semantik baseline (`end < start`); memicu investigasi terarah dan penyimpanan artefak bukti kegagalan tanpa retry liar.
2. **Run Verifikasi Awal / Gagal Sementara (`val_v2_pod_verify_61097`)**: Gagal pada penolakan adapter sementara (Word 100 `Kenapa?`, start 51,4s < previous start 51,8s), fallback Gemini diblokir oleh guard Policy B/B. Durasi tercatat 25,19 detik menurut metadata disk (`12:51:37.160590` s.d. `12:52:02.352872`). Run ini menghasilkan tangkapan diagnostik 1015 kata mentah yang menjadi dasar reproduksi Segmen 86. Izin persetujuan run tambahan berstatus *Belum terkonfirmasi* (tidak ada bukti tertulis terpisah).
3. **Investigasi, Koreksi Adapter, & Suite Regresi**: Identifikasi akar masalah pada baseline `_words_to_segments`, penghapusan durasi minimum buatan, penanganan kata interval nol, hashing streaming pada diagnostik, penolakan tipe boolean, penambahan sanitized fixture, penanganan penerusan *cancellation/timeout* tanpa menelan sinyal kontrol atau memicu fallback, serta penambahan suite regresi 23 unit test (108/108 tes repositori lulus).
4. **Run Verifikasi Sukses — Reuse Audio (`val_v2_pod_verify_61609`)**: Eksekusi sukses penuh menghasilkan 3 klip shorts video dan 3 berkas subtitle WebVTT yang lolos decode penuh FFmpeg (`-xerror`), ketaatan ketat pada batas Policy B/B, serta evaluasi editorial mendalam terhadap framing, subtitle, dan keutuhan narasi.

| Identitas Audit | Nilai Terverifikasi |
| --- | --- |
| Proyek / Tanggal | ShortsStudio / 29 September 2026 |
| Repositori Aktif | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator` |
| Branch / Baseline HEAD | `main` / `fb3aee9b156dabb8ec1b0b14913f189208507766` (dengan patch lokal) |
| Zona Waktu | UTC+07:00 (WIB); timestamp lokal ISO dengan offset eksplisit `+07:00` |
| Dokumen Acuan | [VALIDASI_PEMAKAIAN_NYATA.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/VALIDASI_PEMAKAIAN_NYATA.md), [REVIEW_VALIDASI_VIDEO_1_DAN_RENCANA_VIDEO_2.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_VALIDASI_VIDEO_1_DAN_RENCANA_VIDEO_2.md), [REVIEW_RUNNER_VALIDASI_VIDEO_2.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_RUNNER_VALIDASI_VIDEO_2.md), [REVIEW_VIDEO_2_COLD_RUN_1.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_VIDEO_2_COLD_RUN_1.md), [REVIEW_VIDEO_2_VERIFICATION.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_VIDEO_2_VERIFICATION.md), dan [REVIEW_VIDEO_2_CLOSING.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/REVIEW_VIDEO_2_CLOSING.md) |
| Berkas Produksi Dimodifikasi | `shorts_generator/local/gemini_transcriber.py` dan `shorts_generator/local/transcriber.py` |
| Suite Regresi Baru | `tests/test_v2_transcript_regression.py` (23 unit test, 108/108 tes repositori lulus) |
| Fixture Mandiri | `tests/fixtures/segment_86_sanitized.json` (dapat dijalankan tanpa folder `output_val_v2`) |
| Runner Harness | `scratch\run_validation_v2.py` (menyimpan ringkasan per-job dan ringkasan pointer verifikasi) |
| Direktori Output & Cache V2 | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2\` |
| Cache Video 1 (`output_val_v1\.cache`) | Terverifikasi utuh, tidak disentuh, checksum identik dengan laporan Video 1 |

---

## 1. Spesifikasi Lingkungan dan Pembuktian Isolasi Output/Cache

Pemeriksaan pre-flight dieksekusi dari lingkungan virtual Python aktif (`.venv`) tanpa memanggil API berbayar dan disimpan di `output_val_v2\preflight_v2_check.json`:

| Komponen | Spesifikasi / Path Terverifikasi | Status |
| --- | --- | :---: |
| OS | Windows 11 Home Single Language (10.0.26200-SP0) | Valid |
| CPU | Intel(R) Core(TM) i3-1005G1 CPU @ 1.20 GHz (2 core / 4 threads) | Valid |
| RAM | 12,0 GB nominal (~11,74 GiB tersedia sistem) | Valid |
| GPU | Intel(R) UHD Graphics & NVIDIA GeForce MX330 (2 GB VRAM) | Valid |
| Python Executable | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\.venv\Scripts\python.exe` (v3.11.9) | Valid |
| Paket Runtime Terverifikasi | `google-genai` 2.25.0, `openai` 3.19.2, `opencv-python` 4.14.0, `faster-whisper` 1.2.1, `flask` 3.1.3, `pydantic` 2.13.5 | Valid |
| FFmpeg & FFprobe | Version `N-125875-g5d4d3bdc61-20260731` (Lolos pemeriksaan `-version`) | Valid |
| `shorts_generator.config.LOCAL_OUTPUT_DIR` | Terikat ke `output_val_v2` | Terisolasi |
| `shorts_generator.local.gemini_transcriber.LOCAL_OUTPUT_DIR` | Terikat ke `output_val_v2` | Terisolasi |
| `shorts_generator.local.transcriber.LOCAL_OUTPUT_DIR` | Terikat ke `output_val_v2` | Terisolasi |
| `web_app.OUTPUT_DIR` | Terikat ke `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2` | Terisolasi |
| Audio Cache Path | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2\.cache\audio` | Terisolasi |
| Transcript Cache Path | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2\.cache\transcripts` | Terisolasi |
| Cache Video 1 (`output_val_v1\.cache`) | 3 berkas (1 audio MP3, 2 transcript JSON/SRT), checksum terbukti utuh dan identik | Terlindungi |

---

## 2. Media Sumber Podcast Terverifikasi

Cuplikan video bersumber dari tayangan resmi YouTube Authenticity ID berdurasi 484,00 detik yang memuat percakapan dua pembicara (Soleh Solihun dan Once Mekel):

| Atribut Sumber | Nilai Terverifikasi |
| --- | --- |
| Judul Konten Asli | DINAMIKA PERTEMANAN ONCE MEKEL & AHMAD DHANI - PODCAST NAIK CLAS |
| URL Resmi YouTube | `https://www.youtube.com/watch?v=ClMaZqj8jtI` |
| Jalur Berkas Lokal | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2\source_podcast_v2_clip.mp4` |
| Ukuran & SHA-256 | 51.273.714 byte \| `43ac0f46579386afd6da70db811486eafa61619b0a665e3ef6e8e34eb739a1f2` |
| Durasi Fisik Cuplikan | 484,00 detik (8 menit 4,00 detik) |
| Format Video / Audio | 1280x720, 25 fps, Progressive, H.264 High \| AAC LC stereo 44.100 Hz ~191 kbps |
| Integritas Decode | FFmpeg `-xerror` exit code 0, stderr kosong |
| Karakteristik Pembicara | Dua pembicara dengan percakapan interaktif, transisi antar-shot (wide shot dua orang dan medium shot individual), serta respons backchannel |

---

## 3. Rekapitulasi Seluruh Siklus Eksekusi (3 Job)

Pengujian Video 2 mencakup tiga job terpisah yang tercatat pada disk:

| Parameter | Job 1: `val_v2_pod_37266` (Cold Run 1) | Job 2: `val_v2_pod_verify_61097` (Run Verifikasi Awal) | Job 3: `val_v2_pod_verify_61609` (Run Verifikasi Sukses) |
| --- | --- | --- | --- |
| Waktu (ISO +07:00) | `2026-09-29T06:14:26` s.d. `06:14:50` (23,97s) | `2026-09-29T12:51:37` s.d. `12:52:02` (25,19s disk metadata) | `2026-09-29T13:00:09` s.d. `13:08:41` (511,08s) |
| PID | 7584 | 12948 | 12164 |
| Status / Hasil | **Failed**: Validasi kontrak semantik | **Failed**: Adapter sementara menolak urutan kata | **Completed**: Sukses penuh menghasilkan 3 klip |
| Tahap Kegagalan / Sukses | Validasi semantik transkrip (`end < start`) | Penolakan kata non-monotonik, fallback diblokir | Rendering klip dan finalisasi selesai |
| Gemini Transcribe | 1 inferensi (respons SDK diterima, gagal validasi) | 1 inferensi (rekonstruksi: diagnostik 1015 kata) | 1 inferensi (menghasilkan 998 kata, 128 segmen) |
| Gemini Fallback | 0 (tidak dipanggil) | 0 (diblokir oleh guard sebelum inferensi kedua) | 0 (tidak dipanggil) |
| APMix Highlight | 0 (berhenti sebelum highlight) | 0 (berhenti sebelum highlight) | 2 inferensi (densitas + ranking) |
| Gemini File API | Upload: 1; Delete: 1 (Attempted) | Upload: 1; Delete: 1 (Attempted) | Upload: 1 (`files/51q341zwwj70`); Delete: 1 (Attempted) |
| Izin Persetujuan Run | Disetujui (Rencana awal) | **Belum terkonfirmasi** (tidak ada bukti izin tertulis) | Disetujui (Instruksi pengguna) |
| Klip Dihasilkan | 0 | 0 | 3 klip shorts MP4 + 3 WebVTT |
| Artefak Tersimpan | Folder `..._val_v2_pod_37266` & summary JSON | Folder `..._val_v2_pod_verify_61097` & diagnostik JSON | Folder `..._val_v2_pod_verify_61609` & 3 MP4/VTT |

*Catatan Pengukuran Job 61097*: Durasi 25,19 detik bersumber dari selisih timestamp awal dan akhir pada berkas metadata disk `output_val_v2/20260929_125137_val_v2_pod_verify_61097/job_val_v2_pod_verify_61097.json` (`12:51:37.160590` hingga `12:52:02.352872`). Pengukuran wall-clock runner sebelumnya (24,74 detik) merekam interval proses internal sebelum penulisan metadata disk selesai.

### 3.1 Provenance Analisis Segmen 86
- **Asal Payload**: Analisis matematis terhadap 1015 kata mentah (`raw_words`) bersumber dari berkas diagnostik Job 2: `output_val_v2\20260929_125137_val_v2_pod_verify_61097\diagnostic_transcript_pre_validation_val_v2_pod_verify_61097.json` (tersimpan pukul 12:52:00 WIB), bukan dari Cold Run 1 (`val_v2_pod_37266` pukul 06:14 WIB) yang gagal sebelum mekanisme pencatatan diagnostik diimplementasikan.
- **Reproduksi Mekanisme**: Menjalankan algoritme baseline murni `_words_to_segments` (diekstrak via AST git) terhadap payload 1015 kata secara deterministik menghasilkan 130 segmen dengan anomali pada indeks 86:
  * Kata 674: `"gitu."` (start: 329.8s, end: 330.0s) -> menetapkan `seg_start = 329.8s`.
  * Kata 675: `"Heeh."` (start: 325.8s, end: 325.9s).
  * Kata 676: `"Heeh."` (start: 325.9s, end: 326.0s) -> menutup segmen dengan rentang: **`start: 329.8s`, `end: 326.0s` (`end < start`)**.
- **Batasan Pembuktian**: Rekonstruksi ini membuktikan secara eksak kelemahan mekanisme algoritme baseline pada timestamp mundur (*backward jump*), namun tidak membuktikan kesamaan identitas kata demi kata antara respons Cold Run 1 dan Job 61097.
- **Karakteristik Label Pembicara**: Label pembicara pada respons SDK berstatus kosong; lompatan mundur membuktikan anomali timestamp pada output model, namun atribusi spesifik pembicara A/B dan kepastian sebab akustik (overlap vokal vs kesalahan alignment model) memerlukan evaluasi audio bertimestamp secara terpisah.

---

## 4. Perbaikan Adapter, Penanganan Sinyal Kontrol, & Suite Uji Regresi

Perbaikan diterapkan secara bedah pada tingkat adapter tanpa melonggarkan kontrak semantik:
1. **Modifikasi `shorts_generator/local/gemini_transcriber.py`**:
   - `_parse_offset`:
     * Membedakan secara tegas nilai `None` atau string kosong dari offset valid `0.0`.
     * Menolak tipe `bool` secara eksplisit (`isinstance(val, bool)` diperiksa sebelum pengecekan numerik) sehingga nilai boolean Python tidak diproses sebagai 0 atau 1.
     * Menolak nilai NaN, tak hingga (*infinity*), dan angka negatif dengan pesan diagnostik terarah.
   - `_words_to_segments`:
     * Memvalidasi bahwa setiap kata memiliki `end >= start`.
     * Mendeteksi *backward jump* (`pw["start"] < seg_start`) dan jeda bicara (`pw["start"] - last_word_end > 1.2s`). Saat kondisi ini terjadi, segmen aktif diflush secara bersih sebelum kata berikutnya ditambahkan.
     * Batas segmen dihitung melingkupi seluruh kata di dalamnya: `start = min(w["start"])`, `end = max(w["end"])`.
     * **Penghapusan Durasi Minimum Buatan (Koreksi V2-01)**: Kode `round(max(seg_start + 0.1, seg_end), 2)` dihapus dan diganti menjadi `round(seg_end, 2)`. Batas segmen sepenuhnya ditentukan oleh data kata tanpa durasi fiktif. Kata dengan interval pendek (misal 10,00s–10,02s) tidak lagi diperpanjang sembarangan menjadi 10,10s.
     * **Penanganan Kata Interval Nol**: Kata dengan durasi nol (`start == end`, misal Word 875 pada 422s–422s) diterima secara sah sesuai kontrak (`end >= start`), dipertahankan tanpa durasi buatan, dan tidak didrop.
     * Seluruh segmen disortir kronologis berdasarkan waktu mulai (`segs.sort(key=lambda s: s["start"])`) untuk menjamin urutan monoton naik.
   - `_save_prevalidation_diagnostic`:
     * **Hashing Streaming 64KB (Koreksi V2-02)**: Mengganti pembacaan utuh `Path(media_path).read_bytes()` dengan pembacaan blok 64KB (`while chunk := f.read(65536)`) disertai pemeriksaan checkpoint pembatalan/timeout job context, mencegah pemborosan RAM pada berkas sumber berukuran besar.
     * **Penerusan Exception Kontrol (Koreksi V2-C01)**: `JobCancelledException` dan `JobTimeoutException` secara eksplisit di-re-raise dari dalam loop hashing dan dari handler luar helper, sehingga sinyal penghentian tidak ditelan sebagai kegagalan diagnostik biasa. Berkas diagnostik tidak ditulis bila penghentian terjadi saat hashing.
   - `transcribe_with_gemini`:
     * Pada Path A, exception kontrol `(JobCancelledException, JobTimeoutException)` di-re-raise secara langsung dan **tidak diubah menjadi fallback ke `gemini-3.5-flash`**.
     * Pembersihan berkas remote File API tetap dieksekusi di blok `finally:`.
     * Caller `transcribe_local` tidak menulis transkrip atau mempublikasikan cache bila menerima exception kontrol.
2. **Modifikasi `shorts_generator/local/transcriber.py`**:
   - Menambahkan helper `_validate_transcript_contract_detailed` yang mengembalikan tuple `(bool, Optional[str])` dengan indeks segmen dan alasan eksak penolakan.
3. **Fixture Mandiri & Suite Pengujian Regresi (`tests/test_v2_transcript_regression.py`)**:
   - Menyediakan fixture mandiri yang disanitasi: `tests/fixtures/segment_86_sanitized.json` (988 byte, SHA-256 `6b13f3...`), memungkinkan suite regresi dijalankan secara independen tanpa bergantung pada keberadaan direktori `output_val_v2`.
   - Mengembangkan **23 unit test** yang mencakup:
     * Jeda bicara normal (>1.2s) memisahkan segmen secara bersih.
     * Penolakan `end_offset` dan `start_offset` yang hilang (`None` atau kosong).
     * Penolakan nilai NaN, infinity, dan negatif.
     * Penolakan rentang kata terbalik (`end < start`).
     * Pelindungan kata berdurasi panjang terhadap kata pendek berikutnya.
     * Validasi kontrak rinci dan penolakan struktur segmen invalid.
     * Penolakan penulisan cache sebelum transkrip divalidasi.
     * Penyimpanan diagnostik tanpa kebocoran kredensial.
     * Penanganan kata mundur multi-speaker.
     * Verifikasi integritas payload riil 1015 kata (138 segmen valid).
     * Pencegahan durasi fiktif pada kata pendek (10,00s–10,02s tetap 10,02s).
     * Kebijakan penerimaan kata interval nol (10,0s–10,0s lolos kontrak `end >= start`).
     * Penolakan eksplisit tipe boolean pada offset.
     * Verifikasi kelolosan fixture Segmen 86 tersanitasi.
     * Verifikasi kesamaan hash streaming diagnostik 64KB terhadap hash langsung.
     * **Penerusan sinyal cancel saat hashing diagnostik (tanpa file diagnostik ditulis)**.
     * **Penerusan sinyal timeout saat hashing diagnostik (tanpa file diagnostik ditulis)**.
     * **Penerusan sinyal cancel pada `transcribe_with_gemini` dengan pembersihan File API dan tanpa fallback model**.
     * **Penerusan sinyal timeout pada `transcribe_with_gemini` dengan pembersihan File API dan tanpa fallback model**.
     * **Preservasi cache lama pada `transcribe_local` saat terjadi pembatalan (tanpa publikasi cache baru)**.
     * **Status worker memori dan disk menjadi `CANCELED` (stage: `canceled`) saat pembatalan terjadi**.
     * **Status worker memori dan disk menjadi `TIMEOUT` (stage: `timeout`) saat timeout terjadi**.
   - **Hasil Uji**: Seluruh **23 unit test regresi lulus (100%)** dalam 3,36 detik. Seluruh **108 unit test repositori lulus (100%)** dalam 59,00 detik dengan 0 kegagalan dan 0 regresi.

---

## 5. Profiling Run Verifikasi — Reuse Audio (`val_v2_pod_verify_61609`)

Run verifikasi dieksekusi dengan isolasi penuh dan pemanfaatan cache audio yang sudah teruji:

### 5.1 Metadata Pekerjaan dan Lifecycle
Hasil profiling tercatat pada `output_val_v2\validation_v2_verification_summary.json` dan `output_val_v2\20260929_130009_val_v2_pod_verify_61609\job_val_v2_pod_verify_61609.json`:

| Parameter Eksekusi | Nilai Aktual Terverifikasi |
| --- | --- |
| Job ID | `val_v2_pod_verify_61609` |
| Tipe Run | `Video_2_Podcast_Verification_Run_Reuse_Audio` |
| Folder Sesi | `20260929_130009_val_v2_pod_verify_61609` |
| Process ID (PID) | 12164 |
| Waktu Mulai (ISO +07:00) | `2026-09-29T13:00:09.949801+07:00` |
| Waktu Selesai (ISO +07:00) | `2026-09-29T13:08:41.029693+07:00` |
| Total Durasi Wall-Clock | 511,08 detik (~8 menit 31,08 detik) |
| Durasi Metadata Disk | 511,07 detik |
| Status Akhir In-Memory | `completed` (stage: `completed`) |
| Status Akhir Disk Metadata | `completed` (stage: `completed`) |
| Worker Thread Alive | `False` |
| Active Job Context | `None` (admission lock dilepaskan dengan benar) |

### 5.2 Rincian Interval Eksekusi (Profiling Terperinci)

| Interval Log | Durasi | Persentase | Keterangan |
| --- | :---: | :---: | --- |
| Persiapan & Verifikasi Audio Cache (0.00s–1.25s) | 1,25 s | 0,2% | Menggunakan kembali berkas `audio_source_podcast_v2_clip_cfed8f56508e4c9e.mp3` |
| Unggah Audio ke Gemini File API (1.25s–5.84s) | 4,59 s | 0,9% | Berkas 3,69 MB terunggah dengan ID `files/51q341zwwj70` |
| Inferensi Transkripsi Gemini (5.84s–26.28s) | 20,44 s | 4,0% | Model `gemini-3.5-transcribe` menghasilkan 128 segmen valid (998 kata, ~484,0s) |
| Penyimpanan Diagnostik & File API Delete (26.28s–28.28s) | 2,00 s | 0,4% | Diagnostik tersimpan; delete remote dieksekusi di blok `finally` |
| Analisis Densitas LLM APMix (28.28s–31.83s) | 3,55 s | 0,7% | Mengidentifikasi kategori konten `podcast` dengan densitas `medium` |
| Pemilihan & Pemeringkatan Highlight APMix (31.83s–300.00s) | **268,17 s** | **52,5%** | Bottleneck utama: pemanggilan model DeepSeek via APMix memakan 268 detik |
| Rendering Klip 1 (300.00s–378.65s) | 78,65 s | 15,4% | Face-tracking crop, OpenCV/FFmpeg processing, ASS burning, encoding (64,8s) |
| Rendering Klip 2 (378.65s–437.14s) | 58,49 s | 11,4% | Face-tracking crop, OpenCV/FFmpeg processing, ASS burning, encoding (48,1s) |
| Rendering Klip 3 & Finalisasi (437.14s–511.08s) | 73,94 s | 14,5% | Face-tracking crop, OpenCV/FFmpeg processing, ASS burning, encoding (58,6s) |

*Catatan Prioritas Kinerja*: Tahap analisis/ranking highlight LLM (268,17s atau 52,5%) dan pemrosesan rendering ketiga klip (211,08s atau 41,3%) mendominasi total waktu pengerjaan. Optimasi kecepatan pada fase berikutnya harus memprioritaskan latensi dispatch LLM dan efisiensi pemrosesan frame OpenCV/FFmpeg.

### 5.3 Audit Kuota dan Operasi API

Batasan inferensi runner ditegakkan per proses/job. Rincian audit untuk Job 61609 dan akumulasi seluruh fase Video 2 dicatat secara objektif:

| Komponen API | Batas Per Job | Job 61609 (Attempted / Dispatched / Success) | Total Akumulatif 3 Job | Keterangan & Batasan Bukti |
| --- | :---: | :---: | :---: | --- |
| **Gemini Transcribe** | Maks 1 | 1 / 1 / 1 | 3 inferensi | 1 pada Job 37266, 1 pada Job 61097, 1 pada Job 61609 |
| **Gemini Fallback** | Dilarang | 0 / 0 / 0 | 0 inferensi | Diblokir oleh guard; tidak pernah dipanggil |
| **APMix Highlight** | Maks 2 | 2 / 2 / 2 | 2 inferensi | Hanya dipanggil pada Job 61609 (densitas + ranking) |
| **OpenAI SDK `max_retries`** | Terkunci 0 | - / - / - | - | Terbukti bernilai 0 pada level klien SDK |
| **Gemini File API (Upload)** | Operasi staging | 1 / 1 / 1 | 3 operasi | Terbukti berhasil dengan perolehan remote file ID |
| **Gemini File API (Delete)** | Pembersihan | 1 / 1 / **Attempted** | 3 operasi | **Dicoba di blok `finally`**; runner belum merekam status return/response delete |
| **Token & Biaya Aktual** | - | Belum terukur | Belum terukur | Tidak tersedia data billing/usage resmi; nama model `free` tidak menjadi bukti biaya nol |

---

## 6. Lembar Evaluasi Media (Pasca-Run Verifikasi)

Tiga klip shorts berformat vertikal 9:16 dihasilkan dan lolos uji integritas decode penuh FFmpeg:

| Kriteria Penilaian | Klip 1 (`short_01.mp4`) | Klip 2 (`short_02.mp4`) | Klip 3 (`short_03.mp4`) |
| :--- | :--- | :--- | :--- |
| **Judul AI** | The Royalty Claim Everyone Misread | The Third Reason Is a Punchline | A Friendship Between Countries |
| **Skor Viralitas AI** | 96 | 94 | 91 |
| **Path Berkas MP4** | `output_val_v2\...\short_01.mp4` | `output_val_v2\...\short_02.mp4` | `output_val_v2\...\short_03.mp4` |
| **Ukuran Berkas MP4** | 6.828.918 byte (~6,51 MiB) | 5.704.805 byte (~5,44 MiB) | 7.118.832 byte (~6,79 MiB) |
| **Checksum SHA-256 MP4** | `e3f0553bcd974147e85833dc91a2a6a88219d086c3853d60b044e4f2e05c22d5` | `e10f81619b9c809288f994159e088d2a0ea165d2c871b63977b40a817ed2f68f` | `c630c1dcf0e24c728cb281b25069dc0818df38b4dbc52125610ece953a7c5f47` |
| **Rentang Sumber** | 417,6 s s.d. 482,4 s | 37,1 s s.d. 85,2 s | 110,0 s s.d. 168,6 s |
| **Durasi Fisik (FFprobe)** | 64,80 detik (delta: 0,00 s) | 48,08 detik (delta: -0,02 s) | 58,60 detik (delta: 0,00 s) |
| **Resolusi & Bitstream** | 404x720 (9:16), 25 fps, H.264 \| AAC 44.1kHz | 404x720 (9:16), 25 fps, H.264 \| AAC 44.1kHz | 404x720 (9:16), 25 fps, H.264 \| AAC 44.1kHz |
| **Decode FFmpeg (`-xerror`)** | **Exit 0, stderr kosong (100% valid)** | **Exit 0, stderr kosong (100% valid)** | **Exit 0, stderr kosong (100% valid)** |
| **Path Berkas WebVTT** | `output_val_v2\...\short_01.vtt` | `output_val_v2\...\short_02.vtt` | `output_val_v2\...\short_03.vtt` |
| **Ukuran & SHA-256 VTT** | 2.265 byte \| `35569e...fd16f` | 1.437 byte \| `3f43e7...61ad1` | 1.661 byte \| `19693c...4993` |
| **Jumlah Cue VTT** | 37 cue (header `WEBVTT` valid) | 23 cue (header `WEBVTT` valid) | 29 cue (header `WEBVTT` valid) |
| **Keterurutan Cue VTT** | Terurut monoton naik, dalam durasi klip | Terurut monoton naik, dalam durasi klip | Terurut monoton naik, dalam durasi klip |

---

## 7. Evaluasi 7 Kriteria Mutu Konten Podcast & Status Editorial

Pemeriksaan dilakukan melalui metode obyektif: inspeksi frame statis, metadata FFprobe, dan analisis teks transkrip/VTT, yang dibedakan secara tegas dari pemutaran audiovisual manual menyeluruh (karena audio penuh belum didengar oleh penguji).

1. **Speaker Turns (Pergantian Giliran Bicara ~10 Turn)**:
   - **Status: Terpenuhi Secara Parsial (Perlu Bukti Audio Lintas Sampel).**
   - Dialog percakapan dua arah nyata ada pada media. Pada Klip 2 (`short_02.mp4`), terdapat pertukaran respons antara Soleh Solihun dan Once Mekel terkait alasan jarang wawancara dan punchline persahabatan. Namun penetapan jumlah pasti giliran bicara memerlukan verifikasi audio menyeluruh karena dua baris teks berurutan dapat berasal dari pembicara yang sama.
2. **Auto-Crop Framing / Face Tracking**:
   - **Status: Belum Lulus Keseluruhan (Ditemukan Masalah Kualitas Nyata).**
   - **Klip 1 (Detik 0,5 dan 5,0)**: Sumber adalah wide shot dua pembicara duduk di meja. Algoritme crop mengambil posisi tengah meja/ruangan kosong, sehingga kedua pembicara berada di luar bingkai pada pembuka klip.
   - **Klip 2 (Detik 5,0)**: Pada transisi perubahan shot sumber, wajah subjek di sumber utuh, namun hasil crop memotong wajah pada tepi kanan bingkai.
   - **Klip 3**: Framing lebih stabil dan wajah subjek relatif berada di tengah bingkai vertikal.
3. **Overlap / Backchannel Handling**:
   - **Status: Lolos Logika Integritas; Belum Dinilai Manual Secara Akustik.**
   - Perbaikan rentang waktu adapter berhasil mencegah pembentukan segmen terbalik; WebVTT ketiga klip terbukti tidak memiliki overlap timestamp. Namun ketepatan atribusi teks backchannel dan timing overlap terhadap suara asli belum dinilai manual.
4. **Transcript Accuracy**:
   - **Status: Belum Dinilai Terhadap Ground Truth Audio.**
   - Total 998 kata berhasil ditranskripsikan tanpa crash, mencakup nama diri (*"Oncemichael"*, *"Dani"*) dan istilah institusi (*"LMKN"*). Namun jumlah kata bukan metrik akurasi; tingkat Word Error Rate (WER) terhadap audio belum diukur secara formal.
5. **Subtitle Sync (Pencabutan Klaim Offset ASS/VTT 0 ms)**:
   - **Status: Belum Terukur Terhadap Ucapan Sumber; Klaim 0 ms Dicabut.**
   - **Fakta Implementasi**: Kode pembentukan subtitle pada `clipper.py` menggunakan target kelompok kata yang berbeda: ASS memakai `target_chunk_size = 4` kata, sedangkan VTT memakai `target_chunk_size = 5` kata.
   - Akibatnya, jumlah dan durasi cue berbeda nyata:
     * Klip 1: 42 cue ASS vs 37 cue VTT (misal rentang 0–4,70s dibagi ASS menjadi 3 bagian: 0–1,57, 1,57–3,13, 3,13–4,70; sedangkan VTT membaginya menjadi 2 bagian: 0–2,35 dan 2,35–4,70).
     * Klip 2: 27 cue ASS vs 23 cue VTT.
     * Klip 3: 31 cue ASS vs 29 cue VTT.
   - Klaim sebelumnya bahwa seluruh offset identik 0 ms dicabut karena tidak faktual. Sinkronisasi visual/teks terhadap ucapan sumber asli ($\pm 100\text{ ms}$) berstatus **belum terukur secara perceptual**.
6. **A/V Sync & Lip-Sync**:
   - **Status: Decode & Durasi Aliran Lulus; Lip-Sync Perseptual Belum Dinilai.**
   - Bitstream audio dan video tepat presisi tanpa drift (delta $\le 0,02$ detik) dan lolos decode penuh FFmpeg. Kesesuaian gerak bibir terhadap suara belum dinilai melalui pemutaran audiovisual manual. Kesamaan panjang stream audio/video tidak membuktikan ketiadaan offset perseptual konstan.
7. **Dialog Context / Complete Thought (Keutuhan Gagasan)**:
   - **Status: Klip 1 Menggantung; Klip 2 dan 3 Utuh.**
   - **Klip 1 (64,80s — Melebihi Target Pengujian 15–60s)**: Seleksi berhenti pada 482,4s dengan cue subtitle terakhir `"ROYALTY KEPADA LMKN ATAS"`, memotong frasa penutup pada 482,4s–484,0s (`"lagu-lagu yang dipakai di event itu."`). Terdapat indikasi kuat akhir kalimat menggantung secara editorial berdasarkan teks transkrip.
   - **Klip 2 (48,08s)**: Setup personal hingga penutup komedi (*punchline*) tersampaikan dengan utuh dan natural.
   - **Klip 3 (58,60s)**: Analogi diplomasi antarnegara untuk pertemanan band tersampaikan secara lengkap.

### Ringkasan Status Kesiapan Publikasi per Klip

| Klip | Durasi | Status Kesiapan Publikasi | Masalah Utama yang Ditemukan | Rekomendasi Tindakan |
| :--- | :---: | :--- | :--- | :--- |
| **Klip 1** (`short_01.mp4`) | 64,80 s | **Perlu Edit Besar** | Wide shot meja kosong di pembuka; durasi >60s; kalimat penutup menggantung pada 482,4s. | Pangkas rentang menjadi $\le 60$s pada editor video, perbaiki framing pembuka ke salah satu pembicara, dan pastikan kalimat selesai. |
| **Klip 2** (`short_02.mp4`) | 48,08 s | **Perlu Edit Ringan** | Wajah terpotong di tepi kanan bingkai pada detik ke-5 saat transisi shot sumber. | Geser titik crop horizontal pada detik 4–6 agar wajah subjek tidak terpotong. |
| **Klip 3** (`short_03.mp4`) | 58,60 s | **Belum disahkan siap publikasi; menunggu verifikasi audio** | Framing stabil, gagasan analogi diplomasi utuh; lip-sync perseptual dan kejelasan audio belum diverifikasi penuh. | Lakukan pemutaran audio manual satu kali sebelum diunggah ke platform publik. |

*Catatan Estimasi Waktu*: Estimasi durasi perbaikan manual tidak diisi dengan angka perkiraan/rekaan karena belum dilakukan pengukuran waktu kerja nyata pada editor video eksternal.

---

## 8. Inventaris Bukti Audit dan Checksum SHA-256 Lengkap

Seluruh artefak pembuktian yang dihasilkan selama validasi Video 2 diinventarisasi dengan ukuran biner dan checksum SHA-256 aktual:

| ID Bukti | Jalur Berkas / Artefak | Ukuran (byte) | Checksum SHA-256 | Keterangan & Peran Bukti |
| --- | --- | :---: | --- | --- |
| **V2-RUNNER** | `scratch\run_validation_v2.py` | 24.468 | `5a9a5918645107564434ff73343c2cdac6a4ae128ab038717d81f192e3e95c09` | Runner harness resmi Video 2 dengan guard Policy B/B & per-job summary |
| **V2-REG-TEST** | `tests\test_v2_transcript_regression.py` | 31.737 | `e9f1283a5e3ee265a6d57600f99acda2453bf67ec92ab824e2e72b827373135b` | 23 unit test suite regresi transkripsi, hashing, & propagasi kontrol |
| **V2-MOD-GT** | `shorts_generator\local\gemini_transcriber.py` | 29.898 | `df197f9c4db620e0253895834ff5488b60ec0f45c0fb2c3c20950652cc2ca82b` | Modul adapter dengan perbaikan Segmen 86, durasi, streaming, & kontrol |
| **V2-FIXTURE** | `tests\fixtures\segment_86_sanitized.json` | 988 | `6b13f35c67c9d3d3049b6c3f97548844e11945e761ca9c337b6ec32ab2d3b814` | Fixture mandiri Segmen 86 tersanitasi untuk uji regresi portabel |
| **V2-PREFLIGHT** | `output_val_v2\preflight_v2_check.json` | 3.015 | `8f86d2e3999033f25a639e20e13e17ecf7a18e9a7cc24ae89d3a8efb6cb826b3` | Laporan verifikasi pre-flight tanpa API (Status: PASSED) |
| **V2-SRC** | `output_val_v2\source_podcast_v2_clip.mp4` | 51.273.714 | `43ac0f46579386afd6da70db811486eafa61619b0a665e3ef6e8e34eb739a1f2` | Berkas cuplikan video podcast sumber 484s terverifikasi |
| **V2-AUDIO-CACHE** | `output_val_v2\.cache\audio\audio_source_podcast_v2_clip_cfed8f56508e4c9e.mp3` | 3.873.068 | `271389ddbd8f4b6dafeb4b5ddc398cf42e6a2698f48135c6b792fedc6a257108` | Berkas cache audio mono 16kHz (digunakan ulang di run verifikasi) |
| **V2-CR1-JOB** | `output_val_v2\20260929_061426_val_v2_pod_37266\job_val_v2_pod_37266.json` | 990 | `6a4091a213db62b4ef4cf2ed81a107befe963855e4ee45282133e46f20820d3a` | Metadata disk Cold Run 1 (Status: failed, terpreservasi) |
| **V2-CR1-SUM** | `output_val_v2\validation_v2_summary.json` | 3.985 | `1f16d7daa8b32763a7956c0a2a175e094fd573ce1bc0da059d5aa5541c340a45` | Summary profiling Cold Run 1 (terpreservasi utuh) |
| **V2-JOB2-JOB** | `output_val_v2\20260929_125137_val_v2_pod_verify_61097\job_val_v2_pod_verify_61097.json` | 1.100 | `5ae06c2ca86e4e463e20e0f0fecaf18779ffe15ce6b92f0192d8cab9d8e99d87` | Metadata disk Job 61097 (Status: failed, adapter sementara) |
| **V2-JOB2-DIAG** | `output_val_v2\20260929_125137_val_v2_pod_verify_61097\diagnostic_transcript_pre_validation_val_v2_pod_verify_61097.json` | 129.519 | `e9cddf367f591b0c9a79672df770b2c04c2d0a65a3b2a946e6e5028b7c8888e4` | Sumber empiris diagnostik 1015 kata (asal Segmen 86) |
| **V2-VER-SUM** | `output_val_v2\validation_v2_verification_summary.json` | 9.711 | `bb668f412a79007d52067d6634ac81eb7e7cbb23ae77d4b1a14409909c5515b5` | Summary resmi Run Verifikasi (Status: completed, 3 klip) |
| **V2-VER-JOB** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\job_val_v2_pod_verify_61609.json` | 25.616 | `38af557b7a5611ed8acf6a788a75b951d510efc1644c8eabfb938d62c16d7f12` | Metadata disk Run Verifikasi (Status: completed) |
| **V2-VER-DIAG** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\diagnostic_transcript_pre_validation_val_v2_pod_verify_61609.json` | 143.223 | `853e5da9e57f03a2b55f48f9f931c97c68a86e25abbd053a0b38d8e3d7a1ceb5` | Artefak diagnostik pra-validasi transkrip Job 61609 (tanpa kredensial) |
| **V2-TR-JSON** | `output_val_v2\.cache\transcripts\transcript_source_podcast_v2_clip_7ea695a671ad57fc.json` | 16.268 | `183838c0591dad029d36edbbe3c8f25201d4f583ac500d9d281a943f2bd94314` | Cache resmi transkrip JSON yang valid semantik |
| **V2-TR-SRT** | `output_val_v2\.cache\transcripts\transcript_source_podcast_v2_clip_7ea695a671ad57fc.srt` | 11.108 | `ec9fde0c9f3dc43be9d365875b8a2a72cb385907c22ec1037f9afe725639e03f` | Cache resmi transkrip SRT yang valid semantik |
| **V2-CLIP-01** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\short_01.mp4` | 6.828.918 | `e3f0553bcd974147e85833dc91a2a6a88219d086c3853d60b044e4f2e05c22d5` | Klip short 1 MP4 (64,8s, lolos decode penuh FFmpeg) |
| **V2-VTT-01** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\short_01.vtt` | 2.265 | `35569e88bf700eab651a1e2c3e1f6d3c95eaa93af9a98b1164abbdec534fd16f` | Subtitle WebVTT klip 1 (37 cue terurut) |
| **V2-CLIP-02** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\short_02.mp4` | 5.704.805 | `e10f81619b9c809288f994159e088d2a0ea165d2c871b63977b40a817ed2f68f` | Klip short 2 MP4 (48,1s, lolos decode penuh FFmpeg) |
| **V2-VTT-02** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\short_02.vtt` | 1.437 | `3f43e7f33eded3a42e0c79b399e9cc1e7ba72bbfd968463de139a67ace461ad1` | Subtitle WebVTT klip 2 (23 cue terurut) |
| **V2-CLIP-03** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\short_03.mp4` | 7.118.832 | `c630c1dcf0e24c728cb281b25069dc0818df38b4dbc52125610ece953a7c5f47` | Klip short 3 MP4 (58,6s, lolos decode penuh FFmpeg) |
| **V2-VTT-03** | `output_val_v2\20260929_130009_val_v2_pod_verify_61609\short_03.vtt` | 1.661 | `19693c0766477549fd134dea5a0363cdb2e07df7b4d0bddaa2c4182eca8b4993` | Subtitle WebVTT klip 3 (29 cue terurut) |
| **V1-AUDIO-CACHE**| `output_val_v1\.cache\audio\audio_source_NoDG4oewwjg_720p_a5e65e36c711911b.mp3` | 5.198.156 | `6bf4ba6ea6b5cb3fd046fce2748424685551a968afe1a076bc918ffe174a4faf` | Cache audio Video 1 (terbukti 100% utuh & tidak berubah) |
| **V1-TR-JSON** | `output_val_v1\.cache\transcripts\transcript_source_NoDG4oewwjg_720p_0b58c6212673833a.json` | 23.603 | `f560eb095c88acae54af7ffe5017a726759aca99195eb6c5490fa43d0e6d7f12` | Cache transkrip JSON Video 1 (terbukti 100% utuh) |
| **V1-TR-SRT** | `output_val_v1\.cache\transcripts\transcript_source_NoDG4oewwjg_720p_0b58c6212673833a.srt` | 16.349 | `ec379509ba36347e74b9c44ead78eda939c5499174265d0fa592cf4cb937249c` | Cache transkrip SRT Video 1 (terbukti 100% utuh) |

---

## 9. Kesimpulan Validasi Video 2 & Langkah Selanjutnya

1. **Pipeline & Integritas Media: PASS**
   - Penolakan semantik baseline terbukti benar dan telah diperbaiki pada adapter tanpa melonggarkan kontrak integritas.
   - Durasi buatan telah dihapus, kata berdurasi nol ditangani secara sah, hashing diagnostik dialihkan ke streaming 64KB, penanganan propagasi *cancellation/timeout* diperbaiki tanpa menelan sinyal, dan seluruh 108 pengujian unit repositori lulus 100%.
   - Tiga berkas video MP4 dan tiga WebVTT berhasil dihasilkan dan lolos decode penuh FFmpeg (`-xerror`).
2. **Kualitas Editorial: Perlu Penyesuaian Editorial pada Media yang Ada**
   - Temuan editorial tetap tercatat dan belum dianggap sudah diperbaiki.
   - Klip 1 memerlukan pemangkasan durasi $\le 60$ detik, perbaikan framing wide shot pada pembuka, serta penyesuaian akhir kalimat menggantung.
   - Klip 2 memerlukan penyesuaian crop horizontal pada transisi shot detik ke-5 agar wajah subjek tidak terpotong.
   - Klip 3 berstatus *Belum disahkan siap publikasi; menunggu verifikasi audio*.
   - Seluruh koreksi editorial dapat dieksekusi pada berkas media yang sudah tersedia tanpa melakukan panggilan API berbayar ulang.
3. **Penutupan Teknis Video 2**:
   - Fase validasi Video 2 (Podcast Dua Pembicara) ditutup dengan status **PASS untuk pipeline dan integritas media**, serta catatan editorial yang terpetakan jelas.
   - Repositori siap melangkah ke tahap persiapan dan perencanaan **Video 3 (Video Panjang)** sesuai dokumen [RENCANA_VALIDASI_VIDEO_3_PANJANG.md](file:///C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/RENCANA_VALIDASI_VIDEO_3_PANJANG.md) dengan persetujuan sumber dan batasan API terpisah.
