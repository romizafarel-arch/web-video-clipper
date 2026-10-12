# Laporan Eksekusi Controlled Replay / Resume Validasi Video 3 (Video Panjang)

**Tanggal Eksekusi:** 29 September 2026, 17:37:56 – 17:43:42 WIB  
**Direktori Kerja:** `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
**Git Baseline Commit:** `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e` (`main`)  
**ID Job Replay:** `val_v3_replay_78278`  
**Folder Sesi Output:** `output_val_v3/20260929_173758_val_v3_replay_78278`  
**Status Akhir Replay:** `FAILED` (Tahap Pemeringkatan Highlight Chunk 1 akibat timeout upstream APMix)  
**Dokumen Acuan:**
- `docs/REVIEW_PATCH_TRANSKRIP_VIDEO_3_FINAL.md`
- `docs/REVIEW_CONTROLLED_REPLAY_VIDEO_3.md`
- `docs/LAPORAN_KOREKSI_PATCH_TRANSKRIP_VIDEO_3.md`
- `docs/RENCANA_VALIDASI_VIDEO_3_PANJANG.md`
- Manifest Audit Terkoreksi: `output_val_v3/20260929_173758_val_v3_replay_78278/replay_audit_corrected.json`

---

## 1. Pernyataan Karakter Validasi & Batasan Operasional

> [!IMPORTANT]
> **Karakter Validasi:**  
> Sesuai instruksi dan batas izin, eksekusi ini merupakan **kombinasi dua lingkungan yang berbeda**:
> 1. **Tahap Sanitasi Transkripsi:** Dijalankan secara **offline murni** menggunakan respons STT tersimpan (fixture diagnostik cold run `output_val_v3/20260929_160722_val_v3_long_72842`). Panggilan Gemini STT dan upload File API diblokir ketat di tingkat proses (0 panggilan ke jaringan).
> 2. **Tahap Highlight & Pemeringkatan:** Dijalankan secara **online** menggunakan API eksternal APMix (`deepseek-v4-flash-free` via `https://api.apmix.ai/v1`).
> 
> Eksekusi ini **bukan cold run transkripsi penuh baru**, melainkan controlled replay / resume validasi transkripsi dan highlight.

### Batasan Mandat Eksekusi:
1. **Transkripsi baru:** Tepat 0 inferensi (dijaga interceptor blocking guard).
2. **Upload File API:** Tepat 0 upload (dijaga interceptor blocking guard).
3. **Highlight:** Maksimal 4 inferensi APMix (`deepseek-v4-flash-free` via `https://api.apmix.ai/v1`).
4. **Kebijakan Fail-Fast:** `max_retries = 0`, `MAX_HIGHLIGHT_API_ATTEMPTS = 1`, tanpa retry otomatis SDK/aplikasi, tanpa fallback model, dan tanpa second run otomatis.
5. **Preservasi Absolut:** 65 berkas artefak Video 1 dan Video 2, berkas `.env`, media sumber, dan fixture cold run dilindungi tanpa modifikasi (total 68 berkas terproteksi).

---

## 2. Verifikasi Integritas Media Sumber & Fixture Transkripsi

Sebelum eksekusi dimulai dan setelah proses selesai, checksum SHA-256 dihitung secara streaming dan diverifikasi terhadap referensi yang disahkan:

| Komponen | Path Berkas | SHA-256 Terverifikasi | Status Kecocokan | Durasi Probed (ffprobe) |
| :--- | :--- | :--- | :---: | :---: |
| **Media Sumber Video 3** | `output_val_v3/source_long_v3.mp4` | `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` | **IDENTIK** (Match=True) | 2630.658322 detik (43 menit 50,66 detik, deviasi 0.000000s) |
| **Fixture Diagnostik Cold Run** | `output_val_v3/20260929_160722_val_v3_long_72842/diagnostic_transcript_pre_validation_val_v3_long_72842.json` | `5c0342f33294bd7ae605a76f0e169560c7fe1acfcc7bdd21de3f428aabffade5` | **IDENTIK** (Match=True) | — |

---

## 3. Hasil Sanitasi Transkripsi Offline & Validasi Kontrak

Modul produksi `shorts_generator/local/gemini_transcriber.py` (kebijakan `gemini_recovery_v2_conservative`) dieksekusi secara offline terhadap 5.851 kata mentah dari fixture. Detail metrik di bawah ini telah diselaraskan dengan hasil ekstraksi sanitizer aktual dan dicatat dalam `replay_audit_corrected.json`:

### 3.1. Ringkasan Metrik Sanitasi
- **Total Kata Mentah (Raw Words):** 5.851 kata
- **Total Kata Tersanitasi:** 5.851 kata
- **Kata Pulih Terestimasi (`local_bounded_recovery`):** **Tepat 3 kata** (indeks raw 1228, 1229, 1230)
- **Kata Untrusted:** **Tepat 129 kata**
- **Span Untrusted Terkarantina:** **Tepat 5 span** (durasi gabungan / union: 34,10 detik = 1,30% durasi media)
- **Total Segmen Subtitle Dihasilkan:** **713 segmen**
- **Validasi Kontrak Schema (`_validate_transcript_contract_detailed`):** **LULUS (True)**, 0 pelanggaran struktur/schema.

### 3.2. Detail Kata Pulih Terestimasi (Koreksi V3-R03)
Tepat 3 kata pada indeks raw 1228, 1229, dan 1230 dipulihkan melalui interpolasi terikat konservatif antara dua anchor kata terpercaya (`[512.2s, 512.6s]` pada indeks 1227 dan `[514.6s, 515.2s]` pada indeks 1231), dengan window valid `512.600s .. 514.600s`:

| Indeks Raw | Kata | Offset Mentah (Raw) | Offset Terkoreksi (Estimated) | Aksi & Alasan |
| :---: | :---: | :---: | :---: | :--- |
| **1228** | `"hyper"` | `[516.3, 514.6]` | `[512.600s .. 513.267s]` | `local_bounded_recovery` (`interpolated_in_window(512.60s..514.60s)`) |
| **1229** | `"arousal"` | `[514.6, 515.2]` | `[513.267s .. 513.933s]` | `local_bounded_recovery` (`interpolated_in_window(512.60s..514.60s)`) |
| **1230** | `"hyper"` | `[516.3, 514.6]` | `[513.933s .. 514.600s]` | `local_bounded_recovery` (`interpolated_in_window(512.60s..514.60s)`) |

> *Catatan Koreksi V3-R03:* Narasi sebelumnya yang menyebut indeks 1226–1228 dan anchor 513.78/514.88 telah dikoreksi. Angka di atas merupakan hasil running sanitizer produksi aktual pada fixture Video 3.

### 3.3. Daftar Span Eksklusi untuk Filter Highlight
Daftar span eksklusi kandidat highlight mencakup 5 span untrusted ditambah 1 klaster pemulihan terestimasi (total 6 rentang terlarang):

1. **Eksklusi 1 (Untrusted):** `[1119.9s..1140.1s]` (durasi 20,20s; **57 kata**) — alasan: `window_too_large`, `too_many_words`, `out_of_bounds_in_block`, `temporal_reset_in_block`, `end_spike_or_suspicious_duration`, `raw_deviation_exceeds_window`.
2. **Eksklusi 2 (Untrusted):** `[2009.8s..2012.5s]` (durasi 2,70s; **6 kata**) — alasan: `temporal_reset_in_block`, `end_spike_or_suspicious_duration`, `raw_deviation_exceeds_window`.
3. **Eksklusi 3 (Untrusted):** `[2029.8s..2030.4s]` (durasi 0,60s; **2 kata**) — alasan: `out_of_bounds_in_block`, `end_spike_or_suspicious_duration`, `raw_deviation_exceeds_window`.
4. **Eksklusi 4 (Untrusted):** `[2419.8s..2426.3s]` (durasi 6,50s; **48 kata**) — alasan: `window_too_large`, `too_many_words`, `has_corrupt_tokens`, `end_spike_or_suspicious_duration`, `raw_deviation_exceeds_window`.
5. **Eksklusi 5 (Untrusted):** `[2439.9s..2444.0s]` (durasi 4,10s; **16 kata**) — alasan: `too_many_words`, `temporal_reset_in_block`, `end_spike_or_suspicious_duration`, `raw_deviation_exceeds_window`.
6. **Eksklusi 6 (Klaster Estimasi):** `[512.6s..515.2s]` (durasi 2,60s; 3 kata terestimasi `[512.600s .. 514.600s]`). Klaster eksklusi dikonfigurasi mencakup interval pemulihan terestimasi dan diperluas hingga `515.2s` untuk mencakup konteks batas repetisi cacat (`arousal` `[514.6s..515.2s]`).

*Verifikasi Cakupan Eksklusi:* Klaster `[512.6, 515.2]` secara matematis dan dinamis terbukti 100% mencakup seluruh kata terestimasi `[512.600, 514.600]`.

---

## 4. Audit Guard Interceptor & Verifikasi Blokir Jaringan

Sebelum request highlight dikirim, pengujian aktif guard dilakukan pada runner harness:
- **Interceptor Gemini STT (`Models.generate_content`):** Diuji dengan pemanggilan sintetis. Interceptor berhasil menangkap dan memblokir panggilan dengan `RuntimeError` (`"Semua panggilan inferensi Gemini (gemini-3.5-transcribe) DIBLOKIR..."`). Counter percobaan/dispatched tetap bersih di angka 0.
- **Interceptor Google File API (`Files.upload`):** Diuji dengan pemanggilan sintetis. Interceptor berhasil menangkap dan memblokir panggilan dengan `RuntimeError`. Counter upload tetap 0.
- **Konfigurasi OpenAI Client:** Diuji dan diverifikasi bahwa instance `OpenAI` diinisialisasi dengan `max_retries = 0`.
- **Konfigurasi Highlight Module:** `shorts_generator.highlights.MAX_HIGHLIGHT_API_ATTEMPTS` diverifikasi bernilai 1.

---

## 5. Kronologi Eksekusi Highlight, Konsumsi API, & Analisis Kegagalan

Eksekusi highlight menggunakan model `deepseek-v4-flash-free` via endpoint APMix (`https://api.apmix.ai/v1`).

> [!NOTE]
> **Keterangan Sumber Kronologi:**  
> Tabel kronologi di bawah ini direkonstruksi berdasarkan rekaman stempel waktu log sesi (`replay_execution.log`). Tahap internal yang tidak diinstrumentasi dengan timer monotonik individual dicatat sebagai **"Belum terukur"** (bukan 0.00s terukur).

```text
========================================================================================
Tahap Replay                     Waktu Mulai      Durasi           Status      Catatan
========================================================================================
Inisialisasi & Verifikasi        17:37:56.543     1.52s            SUCCESS     SHA-256 & durasi cocok
Sanitasi Transkripsi Offline     17:37:58.060     Belum terukur    SUCCESS     5.851 kata -> 713 segmen
Uji Coba Guard Interceptor       17:37:58.061     Belum terukur    SUCCESS     STT & File API terblokir
Panggilan 1 (Klasifikasi/Densitas) 17:37:58.062    43.49s           SUCCESS     content=interview, density=medium
Pembagian Chunk Transkripsi      17:38:41.556     Belum terukur    SUCCESS     3 chunk teridentifikasi
Panggilan 2 (Chunk 1/3 Ranking)  17:38:41.557     ~300.00s         TIMEOUT     httpcore2.ReadTimeout / APITimeoutError
Panggilan 3 (Chunk 2/3 Ranking)  —               —                SKIPPED     Dibatalkan (fail-fast)
Panggilan 4 (Chunk 3/3 Ranking)  —               —                SKIPPED     Dibatalkan (fail-fast)
Rendering Klip                   —               —                SKIPPED     0 kandidat terbentuk
========================================================================================
```

### 5.1. Panggilan 1 — Deteksi Jenis Konten & Densitas
- **Waktu Dispatch:** 17:37:58.062 WIB
- **Waktu Respons:** 17:38:41.555 WIB (latensi terukur: 43,49 detik)
- **Status:** **SUKSES**
- **Hasil:**
  - `content_type`: `"interview"`
  - `density`: `"medium"`
- **Konsumsi Kuota Highlight:** 1 dari batas maksimal 4.

### 5.2. Panggilan 2 — Pemeringkatan Kandidat Chunk 1 (0 – 1260 detik)
- **Ukuran Teks Transkrip Chunk 1:** 340 baris teks transkripsi, 20.491 karakter (~3.122 kata).  
  *(Catatan: 20.491 karakter merujuk murni pada teks transkrip Chunk 1, bukan muatan penuh HTTP yang juga memuat prompt sistem, instruksi JSON, dan envelope).*
- **Waktu Dispatch:** 17:38:41.557 WIB
- **Waktu Kegagalan:** ~17:43:41.560 WIB (latensi: ~300 detik)
- **Status:** **TIMEOUT (FAILED)**
- **Pengecualian Teknis:**
  ```text
  httpcore2.ReadTimeout: The read operation timed out
  -> httpx2.ReadTimeout: The read operation timed out
  -> openai.APITimeoutError: Request timed out.
  ```

### 5.3. Analisis Penyebab & Batas Bukti Timeout Panggilan 2
1. **Fakta Terbukti (Mekanisme Timeout Klien):**  
   Pada harness runner awal `scratch/run_controlled_replay_v3.py`, helper penghitung budget request `_get_request_budget_sec()` bergantung pada `active_ctx.started_at`. Namun saat `job_ctx` di-admit oleh `job_manager.admit_job()`, atribut `started_at` belum diisi. Akibatnya, `_get_request_budget_sec()` jatuh ke nilai default `300.0` detik, sehingga `timeout = 300.0` detik diterapkan pada request ke client SDK. Kegagalan terjadi berupa `ReadTimeout` pada socket HTTP setelah 300 detik menunggu data respons.
2. **Status Bukti Latensi Sisi Server (Hipotesis vs Fakta):**  
   Log sesi menunjukkan Panggilan 1 (prompt pendek) selesai dalam 43,49 detik, sedangkan Panggilan 2 (Chunk 1) tidak merespons dalam 300 detik. Dugaan bahwa panjang prompt Chunk 1 menyebabkan waktu pemrosesan melebihi 300 detik berstatus **HIPOTESIS**, bukan kepastian komputasi server. Tanpa telemetri dari penyedia APMix, antrean beban di server, gangguan jaringan/proxy, atau penundaan internal lainnya tidak dapat dipisahkan secara definitif.
3. **Penerapan Ketat Aturan Mandat Fail-Fast:**  
   Karena runner dikonfigurasi dengan `max_retries = 0` dan `MAX_HIGHLIGHT_API_ATTEMPTS = 1`, sistem tidak melakukan retry otomatis ke endpoint, tidak beralih ke model komersial fallback, dan tidak meluncurkan run kedua.

---

## 6. Ringkasan Konsumsi API (Aktual vs Batas Mandat)

| Kategori Operasi API | Batas Mandat | Percobaan (Attempted) | Terkirim ke Jaringan (Dispatched) | Sukses | Gagal | Terblokir (Blocked) | Status Kepatuhan |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Inferensi Gemini STT** | **0** | 0 | 0 | 0 | 0 | 0 | **PATUH 100% (0 inferensi)** |
| **Upload File API** | **0** | 0 | 0 | 0 | 0 | 0 | **PATUH 100% (0 upload)** |
| **Inferensi Highlight APMix** | **Maks 4** | 2 | 2 | 1 | 1 | 0 | **PATUH (2 <= 4 batas)** |

---

## 7. Status Kandidat Highlight & Klip Output

- **Total Kandidat Mentah dari LLM:** 0 (Panggilan Chunk 1 gagal sebelum mengembalikan JSON kandidat).
- **Kandidat Ditolak:** 0.
- **Kandidat Lolos Filter:** 0.
- **Klip MP4 & VTT yang Dirender:** 0 klip.
- **Status Keselarasan Audio-Visual Klip:** **Belum dinilai** (tidak ada klip yang dirender karena pipeline terhenti pada tahap pemeringkatan Chunk 1).

---

## 8. Verifikasi Preservasi Artefak Pasca-Eksekusi

Pengecekan integritas SHA-256 terhadap seluruh inventaris direktori terproteksi dilakukan secara menyeluruh:

| Lingkup Direktori | Jumlah Berkas Terproteksi | Status Pasca-Eksekusi | Keterangan |
| :--- | :---: | :---: | :--- |
| `output_val_v1/` (Validasi Video 1) | 17 berkas | **UTUH 100%** | Checksum identik terhadap baseline |
| `output_val_v2/` (Validasi Video 2) | 48 berkas | **UTUH 100%** | Checksum identik terhadap baseline |
| Berkas Konfigurasi `.env` | 1 berkas | **UTUH 100%** | Checksum identik |
| Media Sumber Video 3 (`output_val_v3/source_long_v3.mp4`) | 1 berkas | **UTUH 100%** | SHA-256: `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` |
| Fixture Cold Run Video 3 (`diagnostic_transcript_pre_validation_val_v3_long_72842.json`) | 1 berkas | **UTUH 100%** | SHA-256: `5c0342f33294bd7ae605a76f0e169560c7fe1acfcc7bdd21de3f428aabffade5` |
| **Total Berkas Terproteksi** | **68 berkas** | **UTUH 100%** | **Preservasi Sempurna (0 diffs)** |

### Keterangan Rekonstruksi & Manifest Koreksi:
- Berkas `job_val_v3_replay_78278.json` dan `validation_v3_replay_summary.json` pada sesi asli merupakan **rekonstruksi pasca-proses** (karena pada harness awal sebelum V3-R01, exception ReadTimeout keluar sebelum finalisasi otomatis menulis berkas metadata).
- Manifest audit definitif yang memuat seluruh hash baseline, metrik sanitasi aktual, dan detail eksklusi adalah `output_val_v3/20260929_173758_val_v3_replay_78278/replay_audit_corrected.json`.

---

## 9. Status Regresi Kode Produksi

Seluruh suite pengujian otomatis proyek dijalankan menggunakan lingkungan virtual Python:
```text
Ran 129 tests in 44.085s
OK
```
- **14 pengujian ketahanan transkripsi Video 3 (`tests/test_v3_transcript_robustness.py`):** 14/14 PASS.
- **7 pengujian replay harness (`tests/test_v3_replay_harness.py`):** 7/7 PASS (mencakup verifikasi offline untuk timeout ranking, timeout klasifikasi, invalid JSON, valid other/medium, inisialisasi clock & budget cap 600s, guard blocking, dan kecocokan manifest).
- **108 pengujian siklus hidup job, verifikasi audio, pembatalan, pemotongan video, dan regresi V1/V2:** 108/108 PASS.
- **Total Regresi:** **0 REGRESI (129/129 PASS, 100% Green)**.

---

## 10. Kesimpulan

1. **Komponen Transkripsi:**  
   Sanitasi offline dan ketahanan struktural transkripsi Video 3 terbukti stabil dan memenuhi kontrak. Modul memproses 5.851 kata dari media 43,8 menit, mengisolasi 5 span cacat (34,10s total gap), memulihkan 3 kata terestimasi (raw index 1228, 1229, 1230), dan menghasilkan 713 segmen yang valid tanpa modifikasi produksi.
2. **Komponen Highlight & Pemeringkatan:**  
   Panggilan 1 (klasifikasi) sukses dalam 43,49s. Panggilan 2 (Chunk 1 ranking) mengalami read timeout pada socket klien (~300 detik). Tidak ada klip yang dirender.
3. **Penyempurnaan Harness & Kesiapan Lanjutan:**  
   Koreksi V3-R01 (clock dan finalisasi lifecycle), V3-R02 (fail-fast guarded classification), dan V3-R03 (penyelarasan manifest dan laporan) telah diselesaikan dan dibuktikan 100% lulus secara offline.
