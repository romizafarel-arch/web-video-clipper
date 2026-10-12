# Rencana Controlled Replay Video 3 melalui API Resmi Kompatibel OpenAI

**Tanggal Penyusunan:** 29 September 2026  
**Direktori Proyek:** `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
**Git Baseline Commit:** `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e` (`main`)  
**Dokumen Acuan:**
- `docs/REVIEW_PERSIAPAN_REPLAY_API_RESMI_FINAL.md` (Sign-off Terbatas Review Independen)
- `docs/REVIEW_PERSIAPAN_REPLAY_API_RESMI.md` (Review Independen Awal)
- `docs/LAPORAN_KOREKSI_PERSIAPAN_REPLAY_API_RESMI.md` (Laporan Koreksi Teknis O-01, O-02, O-03)
- `scratch/run_controlled_replay_v3.py` (Harness Terverifikasi: `033ac2a90a4b5b98ea1f519f47fa1d12bf5f85943b0cfdd984ee746d50b34f00`)

---

## 1. Latar Belakang & Tujuan

Berdasarkan evaluasi independen dan sign-off terbatas pada `docs/REVIEW_PERSIAPAN_REPLAY_API_RESMI_FINAL.md`:
1. Eksekusi controlled replay sebelumnya membuktikan bahwa seluruh guard, penanganan error fail-fast, timeout cap 600s, dan preservasi 68 berkas terproteksi bekerja tertib dan disahkan.
2. Namun, pemeringkatan Chunk 1 gagal akibat HTTP 503 `upstream_unavailable` dari penyedia free-tier APMix.
3. Untuk menguji workload pemeringkatan tanpa mengubah variabel algoritme (tetap menggunakan 3 chunk, prompt yang sama, dan fixture transkripsi yang sama), langkah strategis berikutnya adalah mengalihkan inferensi highlight ke **API resmi yang kompatibel dengan jalur OpenAI SDK**.
4. Validasi Video 3 end-to-end secara faktual **tetap BELUM DITUTUP** sampai ada klip MP4 nyata yang dirender dan dinilai kualitas audiovisualnya (sinkronisasi A/V, subtitle ASS/VTT, dan framing 9:16).

---

## 2. Batasan Mandat Operasional (Strict Enforced)

Replay daring baru hanya akan dijalankan dengan batasan ketat berikut:
- **0 Inferensi Gemini STT:** Panggilan ke `Models.generate_content` tetap diblokir ketat oleh interceptor guard.
- **0 Upload Google File API:** Panggilan ke `Files.upload` tetap diblokir ketat oleh interceptor guard.
- **Maksimal 4 Inferensi Highlight:** Tepat 1 deteksi klasifikasi/densitas dan maksimal 3 pemeringkatan chunk. Panggilan ke-5 akan diblokir otomatis oleh guard.
- **Kebijakan Fail-Fast:** `max_retries = 0`, `MAX_HIGHLIGHT_API_ATTEMPTS = 1`, tanpa retry otomatis, tanpa fallback model lain, dan tanpa second run otomatis.
- **Alokasi Budget Waktu:** Request cap 600.0 detik, shared job budget 1800.0 detik, cadangan perencanaan 60.0 detik.
- **Preservasi Absolut 68 Berkas Terproteksi:** 17 berkas V1, 48 berkas V2, `.env`, media sumber `source_long_v3.mp4`, dan fixture STT cold run terproteksi utuh (0 diffs).

---

## 3. Matriks Opsi Provider Resmi & Perbandingan Tarif

| Parameter | Opsi A (Rekomendasi Utama Pilot): OpenAI Resmi | Opsi B: DeepSeek Resmi (Terkini) |
| :--- | :--- | :--- |
| **Nama Provider** | OpenAI API Resmi | DeepSeek API Resmi |
| **Base URL Kanonikal** | `https://api.openai.com/v1` | `https://api.deepseek.com` |
| **Model Default** | `gpt-4o-mini` | `deepseek-flash` (DeepSeek-V4.1-Flash) |
| **Thinking Mode** | N/A (Standard Chat Completion) | Dinonaktifkan (`disabled`) via `extra_body` |
| **Protokol / SDK** | OpenAI Python SDK (`openai>=1.0.0`) | OpenAI Python SDK (`openai>=1.0.0`) |
| **Variabel Kunci API** | `OPENAI_OFFICIAL_API_KEY` | `DEEPSEEK_API_KEY` |
| **Pemisahan Kredensial** | Terpisah bersih; tidak menggunakan fallback ke `OPENAI_API_KEY` | Terpisah bersih; tidak menggunakan fallback ke `OPENAI_API_KEY` |
| **Karakteristik Latensi** | **Belum diukur pada workload Video 3 ini** | **Belum diukur pada workload Video 3 ini** |
| **Tarif Input Cache Miss** | \$0.15 / 1M token | \$0.30 / 1M token (Peak) \| \$0.15 / 1M token (Off-peak) |
| **Tarif Input Cache Hit** | \$0.075 / 1M token | \$0.006 / 1M token (Peak) \| \$0.003 / 1M token (Off-peak) |
| **Tarif Output** | \$0.60 / 1M token | \$1.20 / 1M token (Peak) \| \$0.60 / 1M token (Off-peak) |
| **Estimasi Biaya Teoritis** | ~ \$0.00231 USD (dengan asumsi 9k in / 1.6k out) | ~ \$0.00231 USD (Off-peak) \| ~ \$0.00462 USD (Peak) |
| **Status Biaya Aktual** | **Belum terukur** (bergantung billing/usage akun pengguna) | **Belum terukur** (bergantung billing/usage akun pengguna) |

> [!NOTE]
> **Sumber Tarif Resmi (Diperiksa 29 September 2026):**  
> - OpenAI GPT-4o-mini: [OpenAI Docs — Models gpt-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini)  
> - DeepSeek Flash: [DeepSeek Documentation — Pricing](https://api-docs.deepseek.com/quick_start/pricing/)  
> *(Menurut sumber resmi saat pemeriksaan, peak DeepSeek berlaku Senin–Jumat pukul 01:00–04:00 dan 06:00–10:00 UTC; waktu lainnya off-peak).*

### 3.1. Rincian Perhitungan Aritmetika Berdasarkan Asumsi Token
Untuk keperluan proyeksi awal, digunakan asumsi volume token perencanaan:
- Call 1 (Klasifikasi): ~1.500 token input, ~100 token output.
- Call 2–4 (Ranking 3 Chunk): ~2.500 token input per chunk, ~500 token output per chunk.
- Total asumsi perencanaan: **9.000 token input (cache miss)** dan **1.600 token output**.

Perhitungan teoritis:
1. **OpenAI `gpt-4o-mini` (Standard):**  
   $$\frac{9.000}{1.000.000} \times \$0.15 + \frac{1.600}{1.000.000} \times \$0.60 = \$0.00135 + \$0.00096 = \$0.00231\text{ USD}$$
2. **DeepSeek `deepseek-flash` (Off-peak):**  
   $$\frac{9.000}{1.000.000} \times \$0.15 + \frac{1.600}{1.000.000} \times \$0.60 = \$0.00135 + \$0.00096 = \$0.00231\text{ USD}$$
3. **DeepSeek `deepseek-flash` (Peak):**  
   $$\frac{9.000}{1.000.000} \times \$0.30 + \frac{1.600}{1.000.000} \times \$1.20 = \$0.00270 + \$0.00192 = \$0.00462\text{ USD}$$

### 3.2. Penegasan Batas: Estimasi vs Pagu yang Ditegakkan
- **Token Asumsi vs Token Aktual:** Angka 9.000 token input dan 1.600 token output di atas adalah **asumsi perancangan**, bukan hasil hitungan tokenizer terhadap prompt final maupun rekaman usage API nyata. Runner saat ini tidak mengekstrak metadata usage per-request secara otomatis; jangan menjanjikan token aktual otomatis tercatat hanya karena inferensi sukses. Jika bukti usage atau billing tidak tersedia dari provider, catat **Belum terukur**.
- **Estimasi Biaya vs Pagu Keras:** Estimasi di atas adalah perkiraan aritmetika teoritis, **bukan batas kuota moneter atau jaminan batas pengeluaran**.
- **Batas Kuantitas Request vs Batas Pengeluaran:** Batas 4 panggilan API highlight adalah batas jumlah operasi jaringan, **bukan jaminan moneter batas biaya total** (karena biaya dipengaruhi oleh panjang prompt dan output model).
- **Mekanisme Penegakan Runner Saat Ini:** Runner saat ini menegakkan **batas operasional struktural**:
  1. Maksimal 4 inferensi highlight (panggilan ke-5 diblokir sebelum mencapai jaringan).
  2. Timeout cap per-request 600.0 detik.
  3. Shared job budget 1800.0 detik dengan cadangan perencanaan 60.0 detik.
  4. `max_retries = 0` dan fail-fast tanpa second run otomatis.
  Runner **belum memiliki mekanisme penegakan pagu uang secara keras (hard dollar cap)**. Jika pengguna menghendaki batas pagu uang keras, eksekusi tidak boleh dimulai sebelum mekanisme pembatasan tersebut disepakati dan diimplementasikan.
- **Status Biaya Aktual:** **Belum terukur** sampai ada verifikasi resmi dari dashboard billing/invoice akun pengguna.

---

## 4. Arsitektur Wrapper & Pembatasan Endpoint Kanonikal

Untuk menjaga integritas harness yang telah disahkan (`scratch/run_controlled_replay_v3.py`), integrasi dilakukan melalui wrapper berukuran kecil:
📁 `scratch/run_controlled_replay_v3_official.py`

### 4.1. Karakteristik Desain:
1. **Zero Production Code Edit:** Tidak ada modifikasi pada direktori `shorts_generator/` maupun runner asli `scratch/run_validation_v3.py`.
2. **Harness Asli Tetap Utuh:** `scratch/run_controlled_replay_v3.py` (SHA-256: `033ac2a90a4b5b98ea1f519f47fa1d12bf5f85943b0cfdd984ee746d50b34f00`) diimpor langsung tanpa modifikasi satu byte pun.
3. **Pewarisan Seluruh Guard & Interceptor:**
   - `_patched_openai_init`: memastikan `max_retries = 0` pada semua instansiasi klien.
   - `_guarded_chat_create`: mengawasi deadline 1800s, request cap 600s, counter API, dan memblokir request ke-5.
   - `_blocked_generate_content` & `_blocked_files_upload`: memblokir panggilan Gemini STT dan upload.
4. **Pengikatan Context Dinamis (O-03):**
   - Mengikat context lookup `_get_active_job_context` secara dinamis ke `effective_jm.get_active_job()`, menjamin pemutusan deadline (< 60s cadangan) aktif pada jalur `override_job_manager`.
5. **Validasi Endpoint Kanonikal & Prosedur Pilot CLI (O-01, O-01.a):**
   - Hanya menerima endpoint resmi kanonikal: `https://api.openai.com/v1` (OpenAI) atau `https://api.deepseek.com` (DeepSeek).
   - Menolak keras URL yang memuat userinfo/kredensial, port non-standar, query string, fragment, atau path non-kanonikal.
   - Pada pilot, jalankan endpoint bawaan tanpa `--base-url` dan tanpa `--api-key`; kunci diberikan melalui environment variable lokal. CLI masih menyediakan kedua opsi tersebut, sehingga larangan ini merupakan prosedur pilot demi keamanan dan isolasi kredensial.

> [!NOTE]
> **Penjelasan Banner Warisan Console (Legacy Console Banner):**  
> Output console stdout yang menampilkan tulisan:  
> `DISPATCHING HIGHLIGHT INFERENCES (APMix deepseek-v4-flash-free)`  
> adalah teks banner log statis yang berasal dari baris log harness warisan `scratch/run_controlled_replay_v3.py`. Demi mematuhi prinsip preservasi berkas terproteksi (SHA-256: `033ac2a9...`), berkas tersebut tidak diubah secara kosmetik. Rute tujuan jaringan dan identitas pemanggilan yang sah secara otoritatif ditentukan oleh payload klien OpenAI SDK dan dicatat pada blok `official_provider` di berkas metadata `job_*.json`.

---

## 5. Hasil Verifikasi Offline Pra-Eksekusi

Pengujian offline dengan respons SDK dimock dan koneksi jaringan diblokir dijalankan melalui test suite:
📁 `tests/test_v3_official_harness.py`

```text
Ran 11 tests in 4.448s
OK
```

Full repository discovery suite:
```text
Ran 143 tests in 44.994s
OK
```

### Komponen yang Terverifikasi:
1. **Resolusi Konfigurasi (test_01):** Default DeepSeek (`deepseek-flash`, `thinking=disabled`) dan OpenAI (`gpt-4o-mini`) benar. Model usang `deepseek-chat` dan `deepseek-reasoner` ditolak dengan `ValueError`.
2. **Propagasi Parameter & Thinking (test_02, test_10):** Inisialisasi klien dengan `max_retries = 0` dan injeksi payload `extra_body={"thinking": {"type": "disabled"}}` untuk DeepSeek Flash.
3. **Budget Bersama & Deadline (test_03):** Pengurangan sisa budget 1800s dan batas cap 600s terbukti tidak direset antar-request.
4. **Blokir STT & Upload (test_04):** Panggilan sintetis ke Gemini STT dan File API upload langsung dilempar `RuntimeError`.
5. **Blokir Request Ke-5 (test_05):** Request highlight ke-5 langsung diblokir sebelum mencapai jaringan.
6. **Fail-Fast Klasifikasi (test_06):** Pelanggaran kontrak klasifikasi seketika menghentikan job pada status `failed`.
7. **Fail-Fast Ranking / Simulasi 503 (test_07):** Pengecualian 503 pada Chunk 1 seketika menghentikan eksekusi tanpa dispatch Chunk 2/3.
8. **Enrichment Metadata (test_08):** Metadata `official_provider` tercatat akurat.
9. **Validasi Endpoint & Isolasi Kredensial (test_09 - O-01, O-01.a):** Endpoint non-HTTPS, APMix, endpoint silang, userinfo, port nonstandar, dan query string ditolak seketika. Kunci generik `OPENAI_API_KEY` tidak pernah digunakan sebagai fallback.
10. **Pengikatan Budget Context override_job_manager (test_11 - O-03):** Sisa waktu <= 60 detik langsung menghentikan eksekusi sebelum dispatch (0 dispatches), menandai status `JobStatus.TIMEOUT`, dan melepaskan admisi.

---

## 6. Prosedur Eksekusi Daring (Setelah Izin Pengguna Diberikan)

Ketika pengguna memberikan izin dan mengonfirmasi variabel kunci API lokal:
1. **Pre-flight Check:**
   - Hitung streaming SHA-256 untuk media sumber, fixture STT, harness, runner asli, dan 68 berkas terproteksi.
   - Cadangkan summary global `output_val_v3/validation_v3_replay_summary.json` dengan penamaan unik baru tanpa menimpa backup sebelumnya.
   - Pastikan variabel kunci API resmi (`OPENAI_OFFICIAL_API_KEY` atau `DEEPSEEK_API_KEY`) terdeteksi di lingkungan lokal pengguna.
2. **Eksekusi Replay:**
   - Jalankan `scratch/run_controlled_replay_v3_official.py` dalam proses Python terpisah dengan parameter provider terpilih menggunakan endpoint bawaan (tanpa `--base-url` dan tanpa `--api-key`).
   - Sesi output baru akan dibuat: `output_val_v3/{timestamp}_val_v3_official_{id}/`.
3. **Penegakan Aturan Eksekusi:**
   - Jika berhasil: lanjut ke pemfilteran kandidat, seleksi top-3, dan perenderan klip MP4 (tanpa `--skip-render`). Lakukan evaluasi penuh terhadap durasi fisik, framing 9:16, subtitle ASS/VTT, potongan narasi, dan sinkronisasi audio-visual.
   - Jika gagal (misalnya rate limit, timeout, atau 503): hentikan seketika (fail-fast), jangan lakukan retry otomatis atau fallback, dan tulis laporan apa adanya.
4. **Pelaporan:**
   - Tulis laporan komprehensif ke `docs/LAPORAN_REPLAY_VIDEO_3_API_RESMI.md`.

---

## 7. Status Pengambilan Keputusan Saat Ini

Sistem saat ini berada dalam posisi **siaga offline murni**. Seluruh perbaikan O-01, O-01.a, O-02, O-03, dan koreksi dokumentasi biaya telah selesai dan diverifikasi. Tidak ada panggilan API daring berbayar yang dijalankan sebelum pengguna memberikan jawaban dan persetujuan tertulis atas pertanyaan konfirmasi pilot.
