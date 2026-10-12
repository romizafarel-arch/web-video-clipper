# Review Independen — Persiapan Controlled Replay Video 3 melalui API Resmi

Tanggal: 29 September 2026  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
Branch/HEAD: `main` — `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`  
Keputusan: **REQUIRES LIMITED CORRECTIONS — wrapper baru belum mendapat sign-off untuk replay berbayar.**

Koreksi laporan replay sebelumnya diterima. Pendekatan wrapper yang memakai harness lama juga sesuai. Tiga koreksi terbatas diperlukan pada konfigurasi resmi, model DeepSeek, dan pengikatan context pada jalur manager terpisah. Bagian A–C, patch transkripsi, serta sign-off harness asli tetap berlaku. Review ini tidak membuka kembali bagian tersebut.

## 1. Lingkup dan metode

Diperiksa implementasi wrapper, suite baru, harness terproteksi, helper LLM produksi, laporan terkoreksi, serta rencana provider. Reviewer menjalankan discovery unittest dengan koneksi socket diblokir, probe konfigurasi, dan OpenAI SDK asli menggunakan `httpx2.MockTransport`. Probe memuat fungsi aktual dari AST tanpa mengubah berkas sumber.

Tes wrapper yang biasanya membuat direktori tetap di repositori diarahkan pada direktori reviewer melalui perubahan variabel runtime. Media/fixture asli tetap menjadi sumber pre-flight; hasil uji tidak menimpa sesi pengguna. Tidak ada inferensi berbayar, upload, pengunduhan media, atau perubahan kode produksi.

Dokumentasi provider diperiksa langsung. Pemeriksaan dokumentasi bukan bukti akses akun, saldo, latensi aktual, maupun kualitas keluaran model untuk transkrip Video 3.

## 2. Keputusan per komponen

| Komponen | Keputusan | Dasar |
| --- | --- | --- |
| Koreksi laporan replay APMix | PASS | Hash, fakta 503 vs hipotesis, biaya belum terukur, interval log, admission, dan status end-to-end telah diperbaiki |
| Penggunaan ulang harness asli | PASS | Harness diimpor, tidak disalin atau diubah; hash cocok |
| Preservasi aset | PASS | 68/68 cocok dengan snapshot review terdahulu; riwayat V3 juga tidak berubah selama pengujian |
| Guard SDK/counter dengan context yang tepat | PASS dalam probe offline | Retry 0, timeout menurun, empat dispatch, request kelima diblokir |
| Kontrak endpoint dan kunci resmi | BELUM PASS | Endpoint arbitrary dan fallback kunci generik masih diterima |
| Default DeepSeek dan klaim kesiapan model | BELUM PASS | Masih memakai alias yang sudah dijadwalkan pensiun sebelum tanggal review |
| Integrasi context pada `override_job_manager` | BELUM PASS | Context manager terpisah tidak ditemukan guard yang membaca singleton global |
| Validasi audiovisual Video 3 | BELUM DITUTUP | Review persiapan offline ini tidak menghasilkan klip replay daring baru |

## 3. Temuan yang wajib ditutup pada wrapper baru

### O-01 — P1: endpoint dan kredensial belum terikat ke provider resmi

Lokasi: [resolver konfigurasi](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_controlled_replay_v3_official.py:67), khususnya penerimaan `base_url` dan fallback kunci pada baris 74.

Resolver hanya melakukan `strip()` terhadap endpoint. Probe aktual menerima semua kombinasi berikut tanpa error:

| Provider yang diklaim | Endpoint yang diterima |
| --- | --- |
| DeepSeek resmi | `https://api.apmix.ai/v1` |
| DeepSeek resmi | `http://example.invalid/v1` |
| OpenAI resmi | `https://example.invalid/v1` |
| OpenAI resmi | `https://api.deepseek.com/v1` |

Nama provider dan metadata tetap bertuliskan resmi. Karena endpoint serta kunci tersebut diteruskan ke SDK, salah konfigurasi dapat mengirim transkrip/kredensial ke tujuan yang berbeda sambil menghasilkan label provider yang keliru. Probe ini tidak mengirim data ke endpoint tersebut; seluruh koneksi nyata diblokir.

Selain itu, ketika `OPENAI_OFFICIAL_API_KEY` tidak tersedia, `OPENAI_API_KEY` tersedia, dan `OPENAI_BASE_URL` kosong, resolver memilih kunci generik untuk endpoint OpenAI resmi. Pemeriksaan substring `apmix` tidak membuktikan asal atau peruntukan kunci. Ini bertentangan dengan mandat pemisahan kredensial; tidak ada bukti kebocoran kunci nyata pada review ini.

**Koreksi minimal:** tetapkan endpoint dari tabel provider, atau izinkan hanya bentuk URL HTTPS resmi yang didokumentasikan untuk masing-masing provider. Hapus fallback otomatis ke `OPENAI_API_KEY`; kunci harus eksplisit atau berasal dari variabel khusus provider. Konfigurasi yang salah harus ditolak sebelum job/request dibuat. Tambahkan regresi endpoint silang, HTTP/nonresmi, dan kunci khusus kosong dengan kunci generik tersedia. Jangan mengubah `.env` untuk menyelesaikan temuan ini.

### O-02 — P1: default `deepseek-chat` tidak sesuai dokumentasi saat ini

Lokasi: [default model wrapper](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_controlled_replay_v3_official.py:41), [rencana provider](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/RENCANA_REPLAY_VIDEO_3_API_RESMI.md:42), dan ekspektasi tes konfigurasi.

Wrapper default, tes, dan rencana masih memakai `deepseek-chat`, bahkan menyebutnya DeepSeek-V3. Pengumuman resmi menyatakan `deepseek-chat` dan `deepseek-reasoner` tidak dapat diakses setelah 24 Juli 2026. Karena review bertanggal 29 September 2026, model tersebut tidak layak dijadikan default replay baru. Ini berdasarkan [pengumuman resmi DeepSeek](https://api-docs.deepseek.com/news/news260424/), bukan hasil request berbayar reviewer.

Dokumentasi terbaru mencantumkan `deepseek-flash`; mode thinking aktif secara default. Mengganti nama model saja tidak mempertahankan perilaku non-thinking dari konfigurasi lama. Jika DeepSeek dipilih, tentukan dan dokumentasikan mode yang digunakan. Untuk pilot yang menekankan waktu serta biaya, non-thinking adalah pilihan awal yang masuk akal, tetapi kualitasnya tetap harus dinilai pada replay. OpenAI SDK mengirim toggle DeepSeek melalui `extra_body`, dan `temperature` diabaikan dalam thinking mode. Lihat [model dan harga DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) dan [parameter thinking](https://api-docs.deepseek.com/guides/thinking_mode/).

**Koreksi minimal:** pakai model resmi yang masih terdokumentasi, selaraskan default/tes/rencana, dan rekam mode serta parameter efektif. Jika diperlukan adaptasi parameter DeepSeek, batasi pada wrapper; jangan mengubah modul produksi atau harness terproteksi. Uji payload SDK dengan transport mock, bukan hanya nama client/model di resolver.

### O-03 — P2: jalur manager terpisah tidak mengikat shared budget ke job yang diuji

Lokasi: [lookup context callable](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_controlled_replay_v3_official.py:97), [penerusan manager](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_controlled_replay_v3_official.py:166), serta [tes integrasi dengan manager terpisah](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/test_v3_official_harness.py:172).

`execute_official_replay` menerima manager terpisah, sedangkan callable dan guard mencari job pada singleton global melalui harness. Tes 06–08 memakai `JobManager()` baru tanpa menghubungkan lookup global ke manager itu. Tes 03 mempatch lookup untuk menguji helper budget, tetapi tidak membuktikan integrasi wrapper tersebut.

Probe memakai job dengan sisa sekitar **29,94 detik**, lebih kecil dari cadangan **60 detik**. Saat job berada pada manager terpisah dan singleton kosong, callable tetap mencapai transport mock dengan timeout **600 detik**. Ketika lookup diikat ke context yang sama, `JobTimeoutException` terjadi dan tidak ada dispatch tambahan.

Sebaliknya, pada context yang terikat dengan benar, SDK asli mengirim timeout 600 detik pada request awal, sekitar 240 detik setelah elapsed 1500 detik, dan memblokir request kelima. Jadi masalahnya adalah pengikatan context jalur override, bukan formula guard yang sudah disahkan. Probe ini tidak menunjukkan bahwa CLI default dengan singleton global gagal.

**Koreksi minimal:** ikat lookup guard/callable ke manager efektif selama eksekusi wrapper, atau hilangkan dukungan override tersebut dan gunakan singleton yang sama pada tes. Tambahkan satu tes integrasi melalui wrapper dengan sisa waktu di bawah cadangan: nol dispatch, status akhir timeout, dan metadata akhir tersedia. Jangan mempatch keluar `Completions.create` yang sedang diuji; mock transport atau fungsi dispatch di bawah guard.

## 4. Koreksi dokumentasi dan catatan pengujian

### Estimasi biaya bukan pagu yang ditegakkan

[Tabel rencana](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/RENCANA_REPLAY_VIDEO_3_API_RESMI.md:46) menyatakan kurang dari USD 0,05 untuk empat inferensi tanpa perhitungan token. Request hasil probe tidak memiliki batas output token eksplisit. Empat request membatasi jumlah operasi, bukan otomatis biaya total.

Hapus angka tersebut sebagai jaminan, atau berikan perhitungan dengan harga model, total input, asumsi/batas output, serta tanggal tarif. Biaya aktual tetap belum terukur sampai ada usage/billing. Jika pengguna memilih pagu uang yang keras, tentukan cara membatasinya sebelum dispatch; jangan menggantinya dengan klaim batas jumlah request saja. Klaim latensi/throughput provider stabil juga harus diberi label belum diukur pada workload ini.

Banner console harness lama masih menyebut APMix pada tes wrapper, walaupun payload resmi dan field `official_provider` memakai tujuan baru. Ini tidak membuktikan request diarahkan ke APMix. Dokumentasikan bahwa banner warisan bukan sumber identitas provider; jangan mengubah harness terproteksi hanya demi menghapus banner tersebut.

### Satu tes lama sensitif terhadap urutan scheduler

Discovery reviewer: **140 tes, 139 lulus, 1 gagal**, dalam **50,130 detik**. Seluruh **8 tes wrapper baru** dan **10 tes harness** lulus dalam discovery tersebut. Tidak ada error atau skip.

Kegagalan berasal dari [assertion urutan editor](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/test_editorial_regression.py:325). Tes menganggap jeda 20 ms memastikan request A memperoleh lock sebelum B. Uji terpisah dengan penjadwalan normal lulus; uji yang menunda masuknya A menghasilkan:

```text
start_B, end_B, start_A, end_A
```

Urutan itu tetap sepenuhnya serial, tetapi assertion gagal. Ini membuktikan tes dapat menolak serialisasi yang sah. Temuan ini adalah kelemahan tes lama, bukan alasan untuk membuka kembali implementasi editor Bagian A. Bila memperbaiki tes, periksa ketidakberirisan pada kedua urutan, atau gunakan sinkronisasi event untuk menguji urutan yang sengaja ditentukan. Jangan melaporkan discovery reviewer sebagai 140/140 PASS.

## 5. Integritas dan bukti

68 berkas terdiri atas 17 berkas V1, 48 berkas V2, `.env`, media Video 3, dan fixture STT. Semuanya cocok dengan snapshot review terdahulu. Sebanyak 17 berkas riwayat V3 yang disnapshot juga tidak berubah selama suite. Tiga modul produksi yang diproteksi cocok dengan review sebelumnya; perbandingan ini bukan klaim bahwa working tree identik dengan Git HEAD sebelum patch transkripsi.

| Berkas | SHA-256 |
| --- | --- |
| Wrapper resmi baru | `cd53535ec709c248a915ccbf8b3bc82ef34485ca60383a2b694d4c095bd407fa` |
| Tes wrapper baru | `6b8a2abc54ddc4e0dc8668fe7d864117a141944ac60fc450e71800676c33b4ab` |
| Harness terproteksi | `033ac2a90a4b5b98ea1f519f47fa1d12bf5f85943b0cfdd984ee746d50b34f00` |
| Runner V3 terproteksi | `3b5e4eef614327a7216bfb72a8cd212541b4bf18b830f75b42c8b3e0a6a306b1` |

Bukti reviewer tersedia di direktori `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`:

- [Log discovery](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_prep_suite.log).
- [Hasil pengujian dan preservasi](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_prep_test_result.json).
- [Probe konfigurasi dan SDK asli dengan transport mock](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_prep_probe_result.json).
- [Probe penjadwalan tes lama](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_old_test_probe_result.json).

## 6. Provider dan kondisi menuju replay

Di antara dua opsi yang diajukan, **OpenAI `gpt-4o-mini` adalah pilihan awal dengan perubahan parameter paling sedikit** pada jalur yang sekarang memakai Chat Completions. Model itu masih tercantum dalam [dokumentasi resmi OpenAI](https://developers.openai.com/api/docs/models/gpt-4o-mini), dengan context 128.000 token dan dukungan Chat Completions. Ini rekomendasi berdasarkan kecocokan integrasi; belum ada bukti kualitas atau kecepatan pada transkrip Video 3 melalui akun pengguna.

DeepSeek resmi tetap dapat dipakai setelah model/mode diperbarui dan diuji offline. Tidak ada kebutuhan mengganti algoritme chunking, fixture, atau produksi untuk menutup tiga temuan ini.

Syarat penutupan persiapan:

1. O-01, O-02, O-03 dikoreksi dan dibuktikan lewat tes offline jalur wrapper.
2. Rencana biaya mencantumkan asumsi/perhitungan atau label belum terukur, bukan jaminan USD 0,05 tanpa dasar.
3. Hasil discovery dilaporkan jujur; kegagalan tes lama dicatat sebagai asumsi urutan scheduler yang sudah direproduksi, atau diperbaiki pada tes tanpa perubahan editor produksi.
4. Preservasi 68 berkas, modul produksi, dan kedua harness tetap cocok.
5. Setelah kesiapan teknis diterima, pengguna memilih provider/model, menyetel kunci khusus secara lokal, dan menyetujui batas API/biaya. Izin replay APMix sebelumnya tidak mencakup replay resmi baru.

Sesudah syarat tersebut dipenuhi, lanjutkan tepat satu replay resmi dengan batas operasi yang sudah ditetapkan dan tanpa retry/fallback otomatis. Penutupan Video 3 end-to-end tetap membutuhkan render nyata dan inspeksi audiovisual; keberhasilan tes offline saja tidak memenuhi syarat itu.
