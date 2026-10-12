# Laporan Patch Ketahanan Transkripsi Gemini — Validasi Video 3 ShortsStudio

**Tanggal**: 29 September 2026 (UTC+07:00)  
**Repositori**: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
**Git Baseline**: `main` — `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`  
**Dokumen Acuan**: `docs/REVIEW_VALIDASI_VIDEO_3_COLD_RUN.md`  
**Fixture Offline**: `output_val_v3/20260929_160722_val_v3_long_72842/diagnostic_transcript_pre_validation_val_v3_long_72842.json` (751.150 byte, 5.851 kata)  
**Versi Kebijakan Sanitizer**: `gemini_recovery_v1_conservative`

---

## 1. Ringkasan Eksekutif & Status Batasan

Sesuai arahan audit independen dan prinsip investigasi ketat (*investigate-first* serta *surgical-patch*):

1. **Lingkup Terbatas & Terisolasi**:
   - Patch hanya diterapkan pada 3 berkas adapter dan konsumen transkrip:
     * `shorts_generator/local/gemini_transcriber.py` (pemulihan konservatif, penandaan gap untrusted, segmentasi aman).
     * `shorts_generator/local/transcriber.py` (validasi kontrak schema transkrip, serialisasi & deserialisasi cache metadata).
     * `shorts_generator/highlights.py` (propagasi span untrusted ke chunk, pemfilteran kandidat highlight yang memotong span untrusted).
   - Tidak ada modifikasi kode pada runner validasi V3 (`scratch/run_validation_v3.py`), Bagian A–C, maupun penutupan teknis Video 2.
2. **Nol Panggilan API Berbayar & Nol Unduhan Media Baru**:
   - Seluruh investigasi, perancangan, dan verifikasi dilakukan **100% offline** menggunakan fixture diagnostik 5.851 kata tersimpan dari cold run `val_v3_long_72842`.
3. **Preservasi Penuh**:
   - Seluruh 65 berkas artefak Video 1 dan Video 2 di `output_val_v1/` dan `output_val_v2/` terverifikasi utuh dengan SHA-256 identik.
   - Seluruh 108 pengujian unit lama + 21 pengujian guard offline + 10 pengujian robustness baru (**total 118 unit tests + 21 guard tests**) lulus 100% tanpa regresi.

---

## 2. Hasil Investigasi Detail Fixture Diagnostik

Audit menyeluruh terhadap 5.851 kata pada durasi video sumber fisik 2.630,658 detik mengonfirmasi temuan auditor:

| Kategori Anomali | Jumlah / Lokasi | Karakteristik & Tindakan Kebijakan |
| --- | --- | --- |
| **Kata Inverted** (`end < start`) | 28 kata | 3 kata terinterpolasi lokal dalam window valid; 25 kata masuk blok ambigu masif. |
| **Start Backward Jump** | 36 kata | Diklasifikasikan: overlap dialog sah (dipertahankan) vs temporal reset masif (ditandai gap). |
| **Endpoint Out-of-Bounds** | 4 kata (12010.1s & 3030.2s) | Ditolak dari interpolasi lokal; ditandai sebagai blok cacat / untrusted gap. |
| **Token Rusak** (`/?`) | 1 token pada indeks 5429 | Ditolak dari interpolasi lokal; ditandai untrusted gap. |
| **Duplikasi Payload Exact** | 0 pada stempel valid | Diuji pada suite unit test (menolak duplikasi identik waktu & penutur). |

### Pemetaan Blok Anomali Masif (Untrusted Spans)
Sesuai rekomendasi reviewer nomor 68, blok anomali masif tidak diratakan atau ditebak digitnya, melainkan ditandai sebagai span yang tidak dapat dipercaya (*untrusted spans*) dan teks mentahnya tetap tersimpan di diagnostik:
1. **Span 1 (`[1119.90s .. 1140.10s]`, durasi 20.20s)**: Indeks 2519–2575 (57 kata). Melibatkan endpoint OOB 12010.1s dan reset masif ke 120–139s di tengah konteks 1119–1140s.
2. **Span 2 (`[2009.80s .. 2012.50s]`, durasi 2.70s)**: Indeks 4611–4616 (6 kata). Reset waktu ke ~1010s di tengah konteks 2009s.
3. **Span 3 (`[2029.80s .. 2030.40s]`, durasi 0.60s)**: Indeks 4660–4661 (2 kata: `emosi kita`). Memiliki endpoint OOB 3030.2s (> durasi 2630.66s). Dilarang menebak digit menjadi 2030.2s sehingga ditandai gap untrusted sepanjang 0.60s.
4. **Span 4 (`[2419.80s .. 2426.30s]`, durasi 6.50s)**: Indeks 5429–5476 (48 kata). Token rusak `/?` dan reset ke 0.2s di tengah konteks 2419s.
5. **Span 5 (`[2439.90s .. 2444.00s]`, durasi 4.10s)**: Indeks 5501–5516 (16 kata). Reset waktu ke 440s di tengah konteks 2439s.

**Total durasi 5 untrusted spans**: 34,10 detik (hanya **1,29%** dari total durasi video 2.630,66 detik, jauh di bawah batas toleransi 25%).

### Pemetaan Pemulihan Lokal Terikat (Local Bounded Recovery)
- **Blok `[1228..1230]` (`hyper arousal hyper`)**:
  - Dibatasi oleh anchor kiri indeks 1227 (`em`, end 512.60s) dan anchor kanan indeks 1231 (`arousal`, start 514.60s).
  - Window durasi = 2,00s (<= 5,0s), jumlah kata bermasalah = 3 (<= 6 kata), laju bicara = 1,50 kata/detik (<= 5,0 kata/detik).
  - Ketiga kata diinterpolasi merata dalam interval `[512.60s, 514.60s]`:
    * 1228 (`hyper`): `512.600s .. 513.267s` (`estimated: True`)
    * 1229 (`arousal`): `513.267s .. 513.933s` (`estimated: True`)
    * 1230 (`hyper`): `513.933s .. 514.600s` (`estimated: True`)
  - Kata ke-4 indeks 1231 (`arousal`) mempertahankan stempel waktu aslinya `514.600s .. 515.200s` secara mulus dan konsisten tanpa perlu diestimasi.

---

## 3. Implementasi Arsitektur Patch

### A. Lapisan Sanitasi & Recovery (`shorts_generator/local/gemini_transcriber.py`)
1. **Pass 1 — Strict Offset Parsing**: Memvalidasi float/int non-null, finite, non-negatif. Tipe boolean, NaN, Infinity, atau negatif ditolak langsung dengan `ValueError`.
2. **Pass 2 — Exact Duplicate Payload Deduplication**: Hanya menghapus duplikasi identik berurutan yang memiliki teks, start, end, dan penutur sama persis, dengan mencatat alasan di audit log.
3. **Pass 3 — Intrinsic Defect Detection**: Mendeteksi rentang terbalik (`end < start`), endpoint melewati durasi sumber fisik (`start/end > source_dur`), serta token rusak (`/?`).
4. **Pass 4 — Temporal Reset Detection**: Mendeteksi penurunan waktu melebihi ambang batas 5,0s terhadap watermark waktu sebelumnya.
5. **Pass 5 — Sandwiched Anomaly Grouping**: Mengelompokkan kata yang terjepit di antara dua anomali agar tidak menjadi anchor palsu.
6. **Pass 6 & 7 — Bounded Recovery vs Untrusted Gap Classification**:
   - Blok cacat dievaluasi terhadap anchor kiri dan kanan yang valid.
   - Syarat interpolasi lokal: `window <= 5.0s`, `count <= 6`, `speech_rate <= 5.0 w/s`, serta tidak mengandung OOB, token rusak, atau temporal reset.
   - Kata hasil interpolasi diberi label `estimated: True` dan dicatat dalam `recovery_audit`.
   - Blok yang tidak memenuhi syarat ditetapkan sebagai `untrusted_spans` dengan rincian indeks, rentang waktu, dan alasan penolakan.
7. **Pass 8 — Quality Gate Tolerance**: Memastikan total durasi untrusted spans tidak melebihi 25% durasi media; jika melebihi, mengangkat `ValueError` kualitas transkrip.
8. **Segment Formation Protection**:
   - `_words_to_segments` mempertahankan segmentasi ketat. Kata untrusted dikeluarkan dari segmen, dan segmen sebelum gap segera di-flush tanpa penyambungan teks lintas gap.
   - Dilakukan asersi akhir bahwa setiap segmen strictly valid (finite, monotonic, non-overlapping with untrusted spans).

### B. Validasi Kontrak Transkrip & Manajemen Cache (`shorts_generator/local/transcriber.py`)
1. `_validate_transcript_contract_detailed`:
   - Menambahkan verifikasi terstruktur terhadap field `untrusted_spans`.
   - Menguji asersi bahwa tidak ada satu pun segmen yang memotong atau tumpang tindih (> 0,05s) dengan rentang span untrusted.
2. `_write_transcript_cache` & `_load_transcript_cache`:
   - Menyimpan field metadata audit (`untrusted_spans`, `recovery_audit`, `policy_version: "gemini_recovery_v1_conservative"`) ke dalam berkas JSON cache transkrip.
   - Menjaga isolasi: transkrip yang melanggar kontrak tidak pernah dipublikasikan ke cache disk.

### C. Proteksi Kandidat Highlight (`shorts_generator/highlights.py`)
1. `chunk_transcript`:
   - Mempropagasi `untrusted_spans` secara proporsional dan relatif ke masing-masing chunk video panjang (dengan offset yang disesuaikan).
2. `_filter_untrusted_highlights`:
   - Menginspeksi setiap kandidat highlight dari model LLM (`start_time .. end_time`).
   - Jika suatu kandidat beririsan dengan span untrusted, kandidat tersebut langsung dibuang disertai pencatatan pesan log job.
3. `get_highlights`:
   - Menjalankan pemfilteran span untrusted **sebelum** deduplikasi highlight, sehingga kandidat valid dengan skor lebih rendah tidak tereliminasi oleh kandidat cacat yang beririsan dengan gap.

---

## 4. Hasil Verifikasi & Pengujian

### A. Pengujian Robustness Transkrip Baru (`tests/test_v3_transcript_robustness.py`)
Dibuat suite pengujian mandiri komprehensif berisi 10 skenario pengujian:
```text
Ran 10 tests in 0.120s
OK
```
1. `test_01_valid_data_preserved_unchanged`: Kata-kata valid tidak mengalami perubahan (0 kata diestimasi, 0 gap untrusted).
2. `test_02_rejection_of_invalid_types_and_numbers`: Tipe `bool`, `NaN`, `Inf`, dan angka negatif ditolak tegas dengan `ValueError`.
3. `test_03_local_bounded_recovery_interpolated_and_flagged`: Jitter lokal terikat berhasil diinterpolasi dan ditandai `estimated: True`.
4. `test_04_out_of_bounds_and_massive_resets_marked_untrusted_spans`: Anomali OOB dan lompatan mundur masif ditolak dari interpolasi dan dijadikan gap untrusted terisolasi.
5. `test_05_valid_dialogue_overlap_preserved`: Overlap penutur sah tidak dipaksa monotonik (`max(prev_end, start)` tidak digunakan); pergantian penutur memisahkan segmen secara bersih.
6. `test_06_exact_duplicate_payload_vs_natural_repetition`: Duplikasi payload identik dibuang dengan audit, sedangkan repetisi alami ucapan dipertahankan.
7. `test_07_highlight_filtering_of_untrusted_spans`: Kandidat highlight yang memotong span untrusted dibuang dari daftar klip.
8. `test_08_chunk_transcript_propagates_untrusted_spans`: Propagasi relatif span untrusted pada chunking video panjang terbukti akurat.
9. `test_09_cache_serialization_and_validation`: Serialisasi cache JSON berhasil menyimpan metadata pemulihan, dan validasi kontrak menolak transkrip yang melintasi gap untrusted.
10. `test_10_offline_diagnostic_fixture_full_replay`:
    - Replay offline penuh pada 5.851 kata fixture cold run Video 3.
    - Hasil: Tepat 3 kata terpulihkan lokal (`estimated: True`), tepat 5 span untrusted teridentifikasi (129 kata, durasi 34,10s = 1,29% durasi video), dan menghasilkan **713 segmen valid**.
    - Kontrak schema transkrip lulus 100% tanpa error.

### B. Pengujian Guard Offline Video 3 (`scratch/test_guards_v3_offline.py`)
```text
Ran 21 tests in 9.092s
OK
```
Semua 21 guard V3 (termasuk cap inferensi highlight 4, blokir fallback STT multimodal, penanganan deadline & cancellation pada wrapper SDK, cleanup File API, serta pemetaan metadata V3-02) lulus 100%.

### C. Regresi Seluruh Suite Unit Test Repositori
```text
Ran 118 tests in 32.645s
OK
```
Semua 108 unit test lama ditambah 10 unit test ketahanan baru lulus secara serentak.

### D. Verifikasi Preservasi Media & Artefak Video 1 dan Video 2
Pemeriksaan SHA-256 pada seluruh 65 berkas artefak terdahulu membuktikan integritas terjaga 100%:
- 17 berkas di `output_val_v1/` identik.
- 48 berkas di `output_val_v2/` (termasuk video sumber `source_podcast_v2_clip.mp4`, 3 short final `short_01.mp4`..`short_03.mp4`, audio MP3, cache transkrip JSON/SRT, dan frame probe) identik.

---

## 5. Ringkasan Perubahan Berkas Produksi

```
shorts_generator/
├── local/
│   ├── gemini_transcriber.py   (+265 baris: recovery algorithm, gap tracking, strict contract)
│   └── transcriber.py          (+35 baris: untrusted_spans schema validation & cache metadata)
└── highlights.py               (+38 baris: relative gap propagation in chunking & candidate filter)
tests/
└── test_v3_transcript_robustness.py (suite baru 10 pengujian robustness)
```

---

## 6. Rekomendasi Tahap Berikutnya: Replay/Resume Terkontrol

Berdasarkan keberhasilan patch ini, sistem telah memiliki ketahanan penuh terhadap respons STT Gemini nyata tanpa mengorbankan ketepatan waktu subtitle atau klip.

**Opsi yang Direkomendasikan**:
Jalankan **Replay/Resume Terkontrol** Video 3 menggunakan respons STT tersimpan dari fixture ini:
- **Tanpa Panggilan Jaringan STT Baru**: Menghindari biaya dan latensi panggilan File API / STT Gemini.
- **Uji Jalur Highlight & Render Nyata**: Menjalankan analisis highlight 3 chunk (maksimal 4 request ke deepseek-v4-flash-free via APMix) dan proses cropping/rendering 3 video Shorts MP4 pada area transkrip yang terpercaya.
- **Label yang Jujur**: Dilaporkan secara transparan sebagai *Controlled Replay Validation*, bukan cold run kedua dari awal.
