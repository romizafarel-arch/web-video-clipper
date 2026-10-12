# Laporan Koreksi Kesiapan Controlled Replay Video 3 melalui API Resmi

**Tanggal:** 29 September 2026  
**Direktori Proyek:** `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
**Git Baseline Commit:** `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e` (`main`)  
**Dokumen Acuan:** `docs/REVIEW_PERSIAPAN_REPLAY_API_RESMI.md` (Review Independen Persiapan Replay Resmi)  
**Status Keseluruhan:** **SELESAI TERVERIFIKASI OFFLINE (100% PASS — SIAP MEMINTA KEPUTUSAN PENGGUNA)**

---

## 1. Ringkasan Eksekutif

Menindaklanjuti review independen pada `docs/REVIEW_PERSIAPAN_REPLAY_API_RESMI.md`, seluruh koreksi terbatas untuk kesiapan teknis Controlled Replay Video 3 melalui API resmi kompatibel OpenAI telah diselesaikan dan dibuktikan secara offline murni:

1. **O-01 (P1) Selesai:** Validasi ketat terhadap endpoint HTTPS resmi (`api.deepseek.com` dan `api.openai.com`), penolakan mutlak endpoint APMix, protokol non-HTTPS, serta endpoint silang provider. Fallback otomatis ke kunci generik `OPENAI_API_KEY` dihapus total demi isolasi kredensial.
2. **O-02 (P1) Selesai:** Default model DeepSeek diperbarui dari alias usang (`deepseek-chat`/`deepseek-reasoner` ditolak secara eksplisit) ke `deepseek-flash` (DeepSeek-V4.1-Flash). Mode thinking dikonfigurasi eksplisit ke `disabled` melalui injeksi payload `extra_body={"thinking": {"type": "disabled"}}` pada OpenAI Python SDK. Model OpenAI dipertahankan `gpt-4o-mini` sebagai alternatif minimalis.
3. **O-03 (P2) Selesai:** Context lookup `_get_active_job_context` diikat secara dinamis ke manager efektif (`effective_jm.get_active_job()`) selama eksekusi wrapper. Terbukti pada tes integrasi dengan sisa waktu <= 60 detik cadangan: pemutusan timeout langsung terjadi sebelum dispatch, menghasilkan 0 dispatch jaringan, status `JobStatus.TIMEOUT`, penulisan metadata, dan pelepasan admisi bersih.
4. **Dokumentasi & Flaky Test Selesai:** Rencana replay diperbarui untuk membedakan estimasi biaya vs pagu struktural yang ditegakkan, mencatat latensi provider belum terukur pada workload ini, serta menjelaskan banner log warisan APMix console. Asumsi jeda waktu scheduler pada `test_editorial_regression.py` diperbaiki sehingga menerima seluruh serialisasi valid (A→B maupun B→A).
5. **Integritas & Zero-Regression:** 143 dari 143 tes lulus pada full discovery suite. 68 berkas terproteksi, harness terproteksi (SHA-256: `033ac2a90a4b...`), dan runner V3 asli (SHA-256: `3b5e4eef6143...`) utuh sempurna. 0 inferensi berbayar, 0 STT call, dan 0 upload dijalankan.

---

## 2. Rincian Penutupan Temuan Review

### 2.1. O-01 — P1: Ikat Endpoint dan Kredensial ke Provider Resmi

* **Berkas Diperbaiki:** `scratch/run_controlled_replay_v3_official.py`
* **Implementasi:**
  1. Menambahkan fungsi `validate_official_endpoint(provider, base_url)`:
     - Memvalidasi protokol wajib `https://`.
     - Menolak setiap URL yang mengandung substring `apmix`.
     - Memvalidasi hostname terhadap whitelist resmi:
       - `deepseek`: `("api.deepseek.com",)`
       - `openai`: `("api.openai.com",)`
     - Menolak endpoint provider silang (misal OpenAI dengan endpoint DeepSeek atau sebaliknya).
  2. Menghapus fallback otomatis ke `OPENAI_API_KEY` di `resolve_official_config()`:
     - Kunci API wajib diberikan secara eksplisit melalui argumen atau variabel lingkungan khusus (`DEEPSEEK_API_KEY` untuk DeepSeek, `OPENAI_OFFICIAL_API_KEY` untuk OpenAI).
     - Jika kunci khusus kosong/tidak disetel, resolver menyetel `api_key = None` dan eksekusi pra-dispatch langsung menolak dengan pesan informatif: `Kunci generik OPENAI_API_KEY tidak digunakan sebagai fallback`.
     - Kunci API tidak pernah dicetak dalam log maupun disimpan dalam metadata publik.
* **Verifikasi:** Diuji pada `test_09_official_endpoint_and_credential_isolation` di `tests/test_v3_official_harness.py`.

### 2.2. O-02 — P1: Default DeepSeek-Flash & Injeksi Parameter Thinking

* **Berkas Diperbaiki:** `scratch/run_controlled_replay_v3_official.py`
* **Implementasi:**
  1. Default model DeepSeek diselaraskan ke `deepseek-flash` (DeepSeek-V4.1-Flash).
  2. Model usang yang telah dipensiunkan (`deepseek-chat` dan `deepseek-reasoner`) ditolak dengan `ValueError` deskriptif.
  3. Mengonfigurasi mode non-thinking (`thinking_mode = "disabled"`) secara default untuk DeepSeek.
  4. Pada `create_official_llm_callable()`, parameter non-thinking diinjeksikan secara tepat sesuai spesifikasi OpenAI SDK:
     ```python
     if config["provider"] == "deepseek" and config.get("thinking_mode") == "disabled":
         create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
     ```
  5. Konfigurasi provider resmi, model, endpoint, dan status thinking dicatat secara transparan pada metadata job (`official_provider`).
* **Verifikasi:** Diuji pada `test_01`, `test_02`, dan `test_10` di `tests/test_v3_official_harness.py`.

### 2.3. O-03 — P2: Pengikatan Context Guard/Budget pada Jalur `override_job_manager`

* **Berkas Diperbaiki:** `scratch/run_controlled_replay_v3_official.py`
* **Implementasi:**
  1. Menambahkan dukungan parameter `override_job_manager` pada `create_official_llm_callable()`.
  2. Pada fungsi `execute_official_replay()`, lookup context global `v3_harness._get_active_job_context` diikat secara dinamis ke manager efektif:
     ```python
     effective_jm = override_job_manager or v3_harness.job_manager
     official_llm = override_llm_fn or create_official_llm_callable(config, override_job_manager=effective_jm)

     orig_context_lookup = v3_harness._get_active_job_context
     def bound_context_lookup():
         try:
             job = effective_jm.get_active_job()
             if job is not None:
                 return job
         except Exception:
             pass
         return orig_context_lookup()

     v3_harness._get_active_job_context = bound_context_lookup
     try:
         disk_meta = v3_harness.execute_controlled_replay(...)
     finally:
         v3_harness._get_active_job_context = orig_context_lookup
     ```
  3. Hal ini memastikan guard `_check_cancel_and_deadline` dan penghitungan `_get_request_budget_sec` membaca sisa waktu job pada manager yang sedang aktif, sehingga ketika sisa waktu <= 60 detik cadangan, eksekusi seketika dibatalkan dengan `JobTimeoutException` sebelum request dispatch highlight dikirim ke transport underlying.
* **Verifikasi:** Diuji pada `test_11_override_job_manager_budget_binding_and_timeout` di `tests/test_v3_official_harness.py`.

---

## 3. Koreksi Dokumentasi dan Resolusi Flaky Test Lama

### 3.1. Penyesuaian Dokumen Rencana Replay Resmi
Dokumen `docs/RENCANA_REPLAY_VIDEO_3_API_RESMI.md` telah diperbarui:
1. **Pembedaan Estimasi Biaya vs Pagu Keras:** Menghapus angka klaim garansi "< USD 0.05". Menyajikan tabel perhitungan berbasis tarif resmi model (DeepSeek Flash input \$0.14/1M, output \$0.28/1M; OpenAI GPT-4o-mini input \$0.15/1M, output \$0.60/1M) dan beban 4 panggilan (~9.000 input, ~1.600 output token) menghasilkan estimasi teoritis ~\$0.001–\$0.004. Status biaya aktual ditegaskan **Belum terukur**. Pagu yang ditegakkan secara teknis adalah batas struktural (maksimal 4 inferensi highlight, timeout cap 600s, shared budget 1800s, max_retries = 0).
2. **Latensi & Throughput:** Ditandai secara eksplisit dengan label **Belum diukur pada workload Video 3 ini**.
3. **Banner Log Warisan APMix Console:** Menjelaskan bahwa teks console `DISPATCHING HIGHLIGHT INFERENCES (APMix deepseek-v4-flash-free)` berasal dari harness terproteksi yang diimpor langsung tanpa modifikasi kosmetik. Identitas provider otoritatif ditentukan oleh payload SDK dan dicatat pada blok `official_provider` di metadata `job_*.json`.

### 3.2. Resolusi Asumsi Scheduler pada Test Editorial Regression
Pada `tests/test_editorial_regression.py` (`test_concurrent_edit_requests_do_not_collide`), assertion lama mengasumsikan thread A selalu memperoleh lock sebelum thread B karena jeda `time.sleep(0.02)`. Pada beban CPU tinggi atau scheduler thread Windows, B dapat dieksekusi lebih dahulu.
Koreksi: Assertion diperbarui untuk memvalidasi ketidakberirisan kedua kemungkinan serialisasi yang sah:
- Urutan 1: Request A selesai penuh sebelum B mulai (`idx_start_a < idx_end_a < idx_start_b < idx_end_b`).
- Urutan 2: Request B selesai penuh sebelum A mulai (`idx_start_b < idx_end_b < idx_start_a < idx_end_a`).
Kode produksi editor tidak disentuh sama sekali.

---

## 4. Hasil Verifikasi Pengujian

### 4.1. Suite Harness Wrapper Resmi (`tests/test_v3_official_harness.py`)
Dieksekusi dengan koneksi jaringan terblokir dan transport SDK dimock:
```text
Ran 11 tests in 3.879s
OK
```
Rincian tes:
- `test_01_config_resolution`: PASS (Resolusi DeepSeek Flash & GPT-4o-mini; penolakan model usang)
- `test_02_llm_callable_and_guards`: PASS (Inisialisasi klien, max_retries=0, extra_body thinking)
- `test_03_timeout_cap_and_shared_budget_decrement`: PASS (Budget bersama & deadline cap 600s)
- `test_04_stt_and_file_upload_blocked`: PASS (Blokir Gemini STT & File API upload)
- `test_05_fifth_highlight_request_blocked`: PASS (Blokir inferensi highlight ke-5)
- `test_06_mocked_classification_failure`: PASS (Fail-fast kontrak klasifikasi)
- `test_07_mocked_ranking_503_failure`: PASS (Fail-fast ranking HTTP 503)
- `test_08_mocked_success_metadata_enrichment`: PASS (Pencatatan metadata provider resmi)
- `test_09_official_endpoint_and_credential_isolation`: PASS (Validasi ketat endpoint O-01 & isolasi kunci)
- `test_10_deepseek_model_and_thinking_payload`: PASS (Verifikasi payload thinking DeepSeek O-02)
- `test_11_override_job_manager_budget_binding_and_timeout`: PASS (Pengikatan deadline context O-03)

### 4.2. Full Repository Test Discovery
Dieksekusi menggunakan runner unit test repositori:
```text
Ran 143 tests in 44.994s
OK
```
Semua 143 tes lulus (100% pass rate, 0 failure, 0 error, 0 skipped).

---

## 5. Verifikasi Integritas dan Checksum

### 5.1. Berkas Kunci
| Berkas | Status | SHA-256 |
| :--- | :---: | :--- |
| `scratch/run_controlled_replay_v3.py` | DIPROTEKSI (Cocok 100%) | `033ac2a90a4b5b98ea1f519f47fa1d12bf5f85943b0cfdd984ee746d50b34f00` |
| `scratch/run_validation_v3.py` | DIPROTEKSI (Cocok 100%) | `3b5e4eef614327a7216bfb72a8cd212541b4bf18b830f75b42c8b3e0a6a306b1` |
| `output_val_v3/source_long_v3.mp4` | DIPROTEKSI (Cocok 100%) | `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` |
| `output_val_v3/.../diagnostic_transcript...json` | DIPROTEKSI (Cocok 100%) | `5c0342f33294bd7ae605a76f0e169560c7fe1acfcc7bdd21de3f428aabffade5` |
| `scratch/run_controlled_replay_v3_official.py` | DIPERBARUI (O-01, O-02, O-03) | `9110edd6a80734de70956dc1c88d13c313d871f08600449f85e387700f059e5e` |
| `tests/test_v3_official_harness.py` | DIPERBARUI (11 tes) | `917d156da268a1f4f8133a6a80fc9471a9539eb3198bcc1ec21cfae1f30f8e67` |
| `tests/test_editorial_regression.py` | DIPERBARUI (Flaky test fix) | `0c322b32e36c27d75bf37b69cda70a4087e92bfaf5ba4107b9684925dba2fdcf` |
| `docs/RENCANA_REPLAY_VIDEO_3_API_RESMI.md` | DIPERBARUI (Dokumentasi) | `d860521c2f67d5e618de50c25d784054221827607eb44c157daf2e9d552c5c6e` |

### 5.2. Preservasi 68 Berkas Terproteksi
Fungsi `snapshot_preservation_manifest()` memverifikasi tepat **68 berkas terproteksi** (17 berkas V1, 48 berkas V2, `.env`, media sumber, dan fixture transkripsi) berada dalam kondisi utuh dan tidak terdistorsi.

---

## 6. Rekomendasi Menuju Replay Daring Resmi

Dengan tuntasnya seluruh koreksi offline, sistem kini siap untuk memasuki tahap controlled replay daring resmi tunggal:

1. **Pilihan Provider Resmi:**
   - **Opsi Rekomendasi Minimalis:** OpenAI API Resmi (`gpt-4o-mini`). Memiliki kompatibilitas chat completions murni tanpa adaptasi parameter custom dan minim risiko format JSON.
   - **Opsi DeepSeek Terkini:** DeepSeek API Resmi (`deepseek-flash`, thinking=disabled). Sangat hemat biaya dan kuat dalam pemrosesan konteks panjang.
2. **Kerahasiaan Kredensial:**
   - Pengguna disarankan menyetel environment variable secara lokal (`DEEPSEEK_API_KEY` atau `OPENAI_OFFICIAL_API_KEY`). Jangan pernah menempelkan API key ke dalam sesi chat.
3. **Konfirmasi & Izin Pengguna:**
   - Menunggu konfirmasi pengguna mengenai provider yang dipilih dan persetujuan eksekusi satu kali (single run) tanpa fallback otomatis.
