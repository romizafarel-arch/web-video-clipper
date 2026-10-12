# Laporan Koreksi Patch Ketahanan Transkripsi Video 3

Tanggal: 29 September 2026 (UTC+07:00)  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
Baseline: `main` / `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`  
Dokumen acuan review: `docs/REVIEW_PATCH_TRANSKRIP_VIDEO_3.md`

---

## 1. Ringkasan Eksekutif

Menindaklanjuti review independen pada `docs/REVIEW_PATCH_TRANSKRIP_VIDEO_3.md`, seluruh empat temuan koreksi (V3-T01 s.d. V3-T04) telah diselesaikan secara tuntas dan konservatif. Perubahan dibatasi secara ketat pada tiga berkas produksi yang sudah terlibat:
1. `shorts_generator/local/gemini_transcriber.py`
2. `shorts_generator/local/transcriber.py`
3. `shorts_generator/highlights.py`

Tidak ada framework baru, provider alternatif, atau dependensi eksternal yang ditambahkan. Tidak ada panggilan API berbayar (Gemini STT maupun APMix LLM) yang dieksekusi selama koreksi ini.

Hasil pengujian otomatis:
- **122/122 unittest lulus** (termasuk 4 tes regresi probe baru untuk V3-T01..V3-T04).
- **21/21 offline guards lulus**.
- **Preservasi 100%**: 65 berkas pada `output_val_v1/` dan `output_val_v2/` tetap identik secara SHA-256. Berkas `.env`, media sumber Video 3, dan fixture diagnostik raw tidak tersentuh.

---

## 2. Rincian Penyelesaian 4 Temuan Review

### V3-T01 — Pengetatan Kelayakan Recovery (P1)

- **Masalah:** Deteksi cacat sebelumnya memakai cabang `if ... elif`, sehingga anomali yang bersamaan `inverted` dan `out_of_bounds` menutupi status OOB. Selain itu, batas media 0 dan EOF disalahartikan sebagai anchor ucapan untuk interpolasi.
- **Solusi yang Diterapkan:**
  1. **Tagging Independen:** Setiap kata cacat mencatat seluruh label secara modular via `Set[str]` (`inverted`, `out_of_bounds`, `corrupt_token`, `suspicious_duration`, `end_spike`, `temporal_reset`). Keberadaan tag `out_of_bounds` pada blok cacat secara permanen menggugurkan eligibility recovery (`out_of_bounds_in_block`).
  2. **Dua Anchor Riil Wajib:** Interpolasi lokal dibatasi ketat hanya jika terdapat dua anchor kata terpercaya (`left_anchor is not None and right_anchor is not None`). Batas 0.0s atau EOF tidak diperbolehkan menjadi pengganti anchor.
  3. **Batas Deviasi Raw Eksplisit:** Parameter `MAX_RAW_DEVIATION_FROM_WINDOW = 5.0` diberlakukan. Setiap kata raw pada blok yang melompat melebihi rentang `[left_time - 5.0, right_time + 5.0]` (baik ke depan maupun ke belakang) ditolak dari recovery (`raw_deviation_exceeds_window`).
- **Verifikasi Regresi (`test_11_v3_t01_strict_recovery_eligibility_and_bounds`):**
  - Sumber 10s; anchor 0–1s & 2–3s; raw 9999–1.5s -> Ditolak recovery, dikarantina ke untrusted span `[1.0, 2.0]`.
  - Sumber 100s; anchor 0–1s & 2–3s; raw 90–1.5s -> Ditolak recovery karena deviasi raw (90s) melebihi window, dikarantina ke untrusted span `[1.0, 2.0]`.
  - Tanpa anchor kiri; raw 90–1.5s disusul kata 2–3s -> Ditolak recovery, dikarantina ke span `[0.0, 2.0]`.
  - Tanpa anchor kanan; kata 18–19s disusul kata terbalik 19.7–19.3s pada media 20s -> Ditolak recovery, dikarantina ke span `[19.0, 20.0]`.

---

### V3-T02 — Deteksi Spike End dan Durasi Mencurigakan Tanpa Merusak Overlap Sah (P1)

- **Masalah:** Kata dengan `raw_end` melompat jauh (seperti probe `11.1–99s` diapit `10–11s` dan `12–13s`) tidak terdeteksi oleh watermark start, sehingga terikut ke segmen 10–99s dan mengotori cache.
- **Solusi yang Diterapkan:**
  1. **Deteksi Durasi Kata Mencurigakan:** Kata dengan durasi melebihi batas batas wajar kata (`MAX_PLAUSIBLE_WORD_DURATION = 10.5s`) diberi label `suspicious_duration`.
  2. **Deteksi End Spike Kontekstual:** End timestamp dievaluasi terhadap tetangga berikutnya: jika `w['raw_end'] > max(next_w['raw_start'], next_w['raw_end']) + MAX_PLAUSIBLE_SPEAKER_OVERLAP` (dengan toleransi `5.0s`), kata ditandai sebagai `end_spike`.
  3. **Preservasi Overlap Percakapan Sah:** Overlap wajar antar pembicara (misalnya pembicara 1: `10.0–13.0s` dan pembicara 2: `12.0–14.0s`, atau backward turn `9.5–12.0s`) tidak dikarantina dan tetap diproses tanpa perataan waktu palsu (`never max(prev_end, start)`).
- **Verifikasi Regresi (`test_12_v3_t02_end_spike_and_suspicious_duration_quarantined`):**
  - Probe reviewer (sumber 100s, `left=10–11`, `spike=11.1–99`, `right=12–13`): `spike` dikarantina menjadi untrusted span `[11.0, 12.0]`. Segmen yang dihasilkan murni `[10.0, 11.0]` dan `[12.0, 13.0]`. Tidak ada segmen yang menjangkau 99s.
  - Kata berdurasi 15s di tengah ucapan dikarantina sebagai span cacat.
  - Overlap percakapan valid terbukti tetap utuh pada `test_05`.

---

### V3-T03 — Penegakan Batas Durasi Media pada Kontrak Cache (P2)

- **Masalah:** Kontrak validator cache sebelumnya tidak mengecek batas atas durasi media, sehingga segmen yang melewati durasi (misal 9–90s pada media 10s) dapat lolos publikasi atau termuat ulang dari disk.
- **Solusi yang Diterapkan:**
  1. **Validasi Upper-Bound:** Parameter `max_duration` ditambahkan ke `_validate_transcript_contract_detailed` dengan toleransi eksplisit `DURATION_TOLERANCE_SECONDS = 0.5`. Seluruh `start` dan `end` segmen serta untrusted spans wajib `<= max_duration + 0.5`.
  2. **Pre-Publish Re-Validation:** Fungsi `_write_transcript_cache` memvalidasi payload metadata final terhadap durasi media yang diprobe (`source_dur`) sebelum berkas JSON dan SRT ditulis ke disk. Pelanggaran durasi langsung melempar `ValueError`.
  3. **Load-Time Gate & Auto-Unlink:** Fungsi `_load_transcript_cache` memvalidasi isi cache terhadap durasi media fisik. Cache yang melanggar durasi langsung di-unlink (`json_path.unlink()`, `srt_path.unlink()`) dan fungsi mengembalikan `None`.
- **Verifikasi Regresi (`test_13_v3_t03_cache_duration_upper_bound_enforcement`):**
  - Upaya penulisan cache dengan segmen 9–90s pada video 10s digagalkan dengan `ValueError: exceeds media duration limit`; tidak ada berkas cache yang terbuat.
  - Berkas cache invalid buatan di disk langsung dihapus saat dibaca dan menghasilkan `None`.
  - Cache valid (9.8s pada video 10s) berhasil ditulis dan dimuat kembali secara identik.

---

### V3-T04 — Penanganan Anchor Overlap dan Union Gap Coverage (P2)

- **Masalah:** Ketika dua anchor di sekitar kata cacat saling tumpang tindih (misal anchor kiri 10–20s dan anchor kanan 16–21s), helper sebelumnya menghasilkan untrusted span terbalik `[20.0, 16.0]` dengan total durasi negatif (-4.0s).
- **Solusi yang Diterapkan:**
  1. **Eksplisit Quality Error:** Jika `left_anchor['end'] > right_anchor['start']`, sanitizer tidak menebak rentang yang kontradiktif melainkan melempar `ValueError` terstruktur:
     `"[transcribe/gemini] Transcript quality error: conflicting overlapping anchors around defective block [start..end] ... Cannot safely determine quarantine boundaries."`
  2. **Bounding Aman untuk Missing Anchors:** Jika anchor kiri absen, batas bawah dikunci ke `0.0`. Jika anchor kanan absen, batas atas dikunci ke durasi media.
  3. **Perhitungan Union Gap:** Fungsi `_calculate_union_span_duration` menggabungkan interval untrusted spans yang beririsan sebelum mengevaluasi fraksi toleransi gap (25%). Durasi terbalik (`end <= start`) diabaikan, mencegah durasi negatif dan penghitungan ganda.
- **Verifikasi Regresi (`test_14_v3_t04_anchor_overlap_and_union_gap_coverage`):**
  - Probe anchor kiri `10–20s`, token rusak `15–15.1s`, anchor kanan `16–21s` melempar `ValueError` berkualitas dengan pesan anchor overlap yang jelas.
  - Pengujian helper union coverage membuktikan:
    - Interval terpisah `[10, 20]` & `[30, 40]` -> `20.0s`.
    - Interval tumpang tindih `[10, 25]` & `[20, 35]` -> `25.0s` (bukan 30s).
    - Interval bersarang `[10, 30]` & `[15, 20]` -> `20.0s`.
    - Interval terbalik `[30, 20]` -> `0.0s` (tanpa durasi negatif).

---

## 3. Hasil Replay Offline Fixture Video 3 (5.851 Kata)

Eksekusi replay fungsi sumber aktual terhadap berkas fixture `diagnostic_transcript_pre_validation_val_v3_long_72842.json` (durasi sumber: 2.630,66 detik):

| Parameter Metrik | Nilai Aktual | Catatan |
|---|---|---|
| Total Raw WordInfo | **5.851 kata** | Respons asli dari cold run |
| Duplicate Words Dropped | **0 kata** | Tidak ada duplikasi payload identik |
| Kata Terevaluasi / Estimated | **3 kata** | Kata `hyper`, `arousal`, `hyper` pada rentang aman 512,6–515,2s |
| Kata Untrusted (Karantina) | **129 kata** | Disimpan pada untrusted spans |
| Untrusted Spans Terbentuk | **5 spans** | Rincian di bawah |
| Total Durasi Gap | **34,10 detik** | **1,30%** dari total durasi media (jauh di bawah batas toleransi 25%) |
| Total Segmen Terbentuk | **713 segmen** | Bersih, sekuensial, tidak melintasi untrusted spans |
| Validasi Kontrak Akhir | **LULUS (True)** | Valid terhadap batas durasi dan integritas schema |
| Kualitas Sinkronisasi Audio | **Belum dinilai** | Belum dilakukan inspeksi dengar audiovisual manusia |

### Rincian 5 Untrusted Spans pada Fixture:
1. `[1119.90s, 1140.10s]` (durasi 20,20s, 57 kata): lonjakan massive reset 12.010,1s & OOB.
2. `[2009.80s, 2012.50s]` (durasi 2,70s, 6 kata): backward jump temporal reset 1.010,1s.
3. `[2029.80s, 2030.40s]` (durasi 0,60s, 2 kata): raw OOB 3.030,2s.
4. `[2419.80s, 2426.30s]` (durasi 6,50s, 48 kata): corrupt token `/?` dan lonjakan temporal reset.
5. `[2439.90s, 2444.00s]` (durasi 4,10s, 16 kata): backward jump temporal reset 440,2s.

---

## 4. Hasil Verifikasi Pengujian Menyeluruh

1. **Unit Test Suite Spesifik (`tests/test_v3_transcript_robustness.py`):**
   - 14/14 test methods lulus (0,345 detik, exit 0).
   - Mencakup tes validasi awal, parsing offset, recovery lokal, tagging defect, overlap dialog, propagasi chunk, serialisasi cache, replay fixture, serta 4 probe V3-T01..V3-T04.
2. **Offline Guards Suite (`scratch/test_guards_v3_offline.py`):**
   - 21/21 guard tests lulus (10,627 detik, exit 0).
   - Memastikan tidak ada regresi pada perlindungan abort, signal handling, staging media, dan boundary safety.
3. **Repository Full Unittest Discovery (`python -m unittest discover -s tests`):**
   - 122/122 test methods lulus (36,126 detik, exit 0).
4. **Preservasi Aset Historis:**
   - 65 berkas pada `output_val_v1/` dan `output_val_v2/` terverifikasi utuh dengan SHA-256 identik.
   - `.env` utuh.

---

## 5. Kesimpulan dan Status Kesiapan

Seluruh empat butir koreksi independen dari `docs/REVIEW_PATCH_TRANSKRIP_VIDEO_3.md` telah diselesaikan secara presisi, teruji melalui probe regresinya masing-masing, dan diverifikasi tanpa efek samping pada seluruh suite proyek.

Patch ketahanan transkripsi Video 3 kini berstatus **siap untuk tahap review independen akhir dan sign-off controlled replay / resume validasi Video 3**.
