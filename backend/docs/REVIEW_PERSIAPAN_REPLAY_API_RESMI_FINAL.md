# Review Penutup Kesiapan Controlled Replay Video 3 melalui API Resmi

Tanggal: 29 September 2026  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`  
Branch/HEAD: `main` — `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`

## 1. Keputusan resmi

**SIGN-OFF TERBATAS: kesiapan teknis diterima untuk tepat satu pilot dengan endpoint bawaan provider dan konfigurasi yang ditetapkan di bawah.**

Perbaikan inti O-01, O-02, dan O-03 telah dibuktikan. Reviewer menjalankan discovery lengkap: **143/143 tes lulus dalam 40,062 detik, tanpa failure, error, atau skip**. Sebelas tes wrapper resmi dan sepuluh tes harness asli termasuk dalam hasil tersebut. Probe independen melalui SDK asli dengan transport mock membuktikan payload, pengurangan budget, penolakan dispatch saat cadangan habis, finalisasi metadata, dan pemulihan context lookup.

Ini bukan sign-off tanpa batas untuk setiap variasi `--base-url`. Ada dua catatan terbatas: validator masih menerima URL berkredensial/port/path/query tambahan, dan tarif DeepSeek pada dokumen rencana belum sesuai tarif resmi yang ditemukan saat review. Catatan tersebut dijelaskan di bagian 3. Pilot menggunakan endpoint bawaan sehingga tidak memerlukan pembukaan ulang arsitektur atau Bagian A–C.

Sign-off teknis ini juga **bukan izin mengeksekusi API berbayar**. Eksekusi menunggu keputusan pengguna mengenai provider/model, kunci lokal, dan batas penggunaan/biaya berdasarkan informasi tarif yang benar. Validasi Video 3 end-to-end tetap belum ditutup karena review ini tidak menghasilkan atau menilai klip replay daring baru.

## 2. Matriks evaluasi temuan

| Item | Status | Bukti dan batas penilaian |
| --- | --- | --- |
| O-01: host resmi, HTTPS, isolasi kunci | PASS untuk profil pilot | Host nonresmi, APMix, HTTP, dan endpoint silang ditolak; kunci generik tidak diambil. Validasi seluruh komponen URL belum lengkap, lihat O-01.a |
| O-02: model DeepSeek dan thinking | PASS untuk default `disabled` | Alias lama ditolak; model `deepseek-flash`; SDK benar-benar mengirim `thinking: {type: disabled}` |
| Alternatif OpenAI | PASS offline | SDK mengirim `gpt-4o-mini` ke `/v1/chat/completions` tanpa field thinking khusus DeepSeek |
| O-03: manager efektif dan shared budget | PASS | Empat dispatch pada manager terpisah menggunakan budget yang sama; sisa 30 detik menghasilkan nol dispatch dan status timeout |
| Pemulihan context lookup | PASS | Fungsi asli dipulihkan sesudah sukses, timeout, dan exception yang keluar dari harness |
| Koreksi dokumentasi | DITERIMA DENGAN KOREKSI TARIF | Biaya aktual belum terukur, latensi belum diuji, dan banner warisan sudah dijelaskan. Angka tarif DeepSeek perlu mengikuti bagian 3.2 |
| Tes editor yang sensitif scheduler | PASS | Urutan A→B dan B→A sama-sama lulus; assertion tetap menolak operasi yang beririsan |
| Preservasi 68 berkas | PASS | Seluruhnya cocok dengan snapshot review terdahulu; 23 berkas riwayat V3 juga tetap sama selama suite |
| Integritas produksi dan harness | PASS | Tiga modul produksi terproteksi dan kedua harness cocok dengan review sebelumnya |
| Kualitas audiovisual Video 3 | BELUM DINILAI pada replay resmi | Semua respons inferensi pada review ini sintetis; rendering replay baru tidak dijalankan |

### 2.1. Bukti SDK dan budget

Probe memakai **OpenAI SDK asli** dan `httpx2.MockTransport`, dengan koneksi socket nyata diblokir. Guard `Completions.create` tetap dijalankan; reviewer tidak menggantinya dengan respons langsung pada probe integrasi.

| Kasus | Hasil |
| --- | --- |
| DeepSeek default | `https://api.deepseek.com/chat/completions`, model `deepseek-flash`, thinking `disabled` |
| OpenAI default | `https://api.openai.com/v1/chat/completions`, model `gpt-4o-mini`, tanpa field thinking |
| Retry SDK | `max_retries=0` |
| Request pertama pada job normal | Timeout SDK 600 detik |
| Setelah elapsed 1500 detik diinjeksi sebagai fixture offline | Timeout request berikutnya sekitar 239,997 detik; budget yang sama tidak direset |
| Job pada manager terpisah dengan sisa 30 detik | Transport tidak dipanggil; status memori dan disk `timeout`; admission dilepas |
| Setelah wrapper selesai/exception | Context lookup kembali ke fungsi semula |
| Kunci dummy melalui argumen normal | Tidak ditemukan pada metadata hasil maupun stdout probe |

Elapsed 1500 detik di atas adalah simulasi waktu untuk menguji deadline, bukan latensi layanan atau waktu pemrosesan Video 3 nyata. Timeout scalar SDK berlaku pada operasi HTTP; angka 600 detik tidak boleh dilaporkan sebagai bukti stopwatch mutlak end-to-end satu request. Pemeriksaan deadline sebelum/sesudah request tetap bekerja sebagaimana harness yang sudah disahkan.

### 2.2. Perbaikan tes editor

[Assertion terbaru](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/test_editorial_regression.py:319) memeriksa salah satu dari dua urutan yang sepenuhnya serial. Reviewer menjalankan ulang tes dengan scheduler normal dan dengan request A sengaja ditunda:

```text
Normal:           start_A, end_A, start_B, end_B  -> PASS
B berjalan dulu:  start_B, end_B, start_A, end_A  -> PASS
```

Perubahan terbatas pada tes; editor produksi tidak diubah. Jeda scheduler tidak lagi menentukan kelulusan assertion.

## 3. Catatan tersisa dan pembatasan sign-off

### 3.1. O-01.a — P2: URL khusus masih dapat membawa kredensial yang tercetak

Lokasi: [validator endpoint](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_controlled_replay_v3_official.py:66) dan [pencetakan endpoint](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_controlled_replay_v3_official.py:223).

Validator memeriksa scheme dan hostname, tetapi belum menolak userinfo, port tambahan, path nonkanonikal, atau query. Probe menerima antara lain:

```text
https://review-user:dummy-url-secret@api.openai.com/v1
https://api.openai.com:8443/v1
https://api.openai.com/unrelated-path
https://api.openai.com/v1?token=dummy-url-secret
```

Eksekusi dry-run yang harness-nya dimock menunjukkan penanda `dummy-url-secret` dari userinfo ikut tercetak di stdout karena URL dicetak utuh. Penanda tersebut sepenuhnya sintetis; tidak ada bukti kunci pengguna bocor dalam review ini. Penghapusan fallback generik dan penolakan host silang tetap benar.

**Batas operasional pilot:** jangan memberikan `--base-url` atau endpoint override programatik. Gunakan hanya default `https://api.openai.com/v1` atau `https://api.deepseek.com`. Jangan menaruh kunci/token pada URL. Dengan profil itu, jalur bocor yang direproduksi tidak digunakan.

Sebelum mengklaim validasi URL umum sepenuhnya ketat, perbaiki validator agar hanya menerima bentuk endpoint resmi yang disepakati, tanpa username/password, query, fragment, port nonstandar, atau path lain. Solusi paling kecil adalah allowlist URL kanonikal. Ini catatan pada fleksibilitas endpoint wrapper baru, bukan kegagalan guard budget atau alasan membuka kembali editor/pipeline yang ditutup.

### 3.2. D-01 — P2 dokumentasi: tarif DeepSeek masih salah

[Rencana terbaru](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/RENCANA_REPLAY_VIDEO_3_API_RESMI.md) sudah membedakan estimasi dari batas yang ditegakkan, tetapi angka DeepSeek USD 0,14/input dan USD 0,28/output per sejuta token tidak cocok dengan tarif resmi yang ditemukan saat review.

Tarif untuk perbandingan, USD per sejuta token:

| Model/kondisi | Input cache miss | Input cache hit | Output |
| --- | ---: | ---: | ---: |
| DeepSeek Flash, peak | 0,30 | 0,006 | 1,20 |
| DeepSeek Flash, off-peak | 0,15 | 0,003 | 0,60 |
| OpenAI GPT-4o-mini, standard | 0,15 | 0,075 | 0,60 |

Sumber: [tarif resmi DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/) dan [OpenAI Docs untuk GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini). Halaman DeepSeek terindeks resmi tersedia pada pencarian saat review; pengambilan ulang halaman pricing secara langsung mengalami timeout. Dokumentasi tersebut juga telah diperiksa pada review sebelumnya dalam sesi ini. Angka di atas tidak berasal dari billing akun pengguna dan tetap perlu diperiksa sebelum keputusan pengeluaran.

Memakai **asumsi dokumen**, yaitu total 9000 token input cache miss dan 1600 token output, hasil aritmetikanya:

| Opsi | Perhitungan | Estimasi USD |
| --- | --- | ---: |
| DeepSeek peak | `9000/1e6 × 0,30 + 1600/1e6 × 1,20` | 0,00462 |
| DeepSeek off-peak | `9000/1e6 × 0,15 + 1600/1e6 × 0,60` | 0,00231 |
| GPT-4o-mini standard | `9000/1e6 × 0,15 + 1600/1e6 × 0,60` | 0,00231 |

9000/1600 token masih asumsi, belum merupakan hitungan tokenizer dari prompt final atau usage API nyata. Estimasi bukan jaminan biaya dan bukan pagu keras. Batas empat request tidak membatasi output token secara moneter. Perbarui dokumen rencana sebelum meminta persetujuan biaya; angka yang dikoreksi pada laporan review ini dapat menjadi acuan sementara. Hindari konversi Rupiah tanpa kurs/tanggal yang jelas.

Jika pengguna meminta pagu uang yang benar-benar keras, jangan mengklaim runner sekarang sudah menegakkannya. Tentukan batas token dan mekanisme pengeluaran yang sesuai terlebih dahulu, atau nyatakan batas operasional yang benar-benar ada dan minta persetujuan berdasarkan itu.

## 4. Penilaian provider dan rekomendasi

| Aspek | OpenAI `gpt-4o-mini` | DeepSeek `deepseek-flash` |
| --- | --- | --- |
| Endpoint pilot | `https://api.openai.com/v1` | `https://api.deepseek.com` |
| Parameter khusus | Tidak perlu toggle DeepSeek | `thinking.type=disabled`, sudah terbukti masuk payload |
| Bentuk pemanggilan | Chat Completions melalui SDK yang sama | Chat Completions melalui SDK yang sama |
| Parser dan prompt | Memakai kontrak dan prompt harness yang sama | Memakai kontrak dan prompt harness yang sama |
| Latensi workload Video 3 | Belum diukur | Belum diukur |
| Kualitas highlight Indonesia pada fixture ini | Belum diuji daring | Belum diuji daring |
| Akses akun, saldo, batas akun | Belum diverifikasi oleh reviewer | Belum diverifikasi oleh reviewer |

`gpt-4o-mini` masih terdokumentasi mendukung Chat Completions; `deepseek-flash` merupakan nama model yang didokumentasikan untuk V4.1-Flash. Default mode DeepSeek adalah thinking, sehingga toggle `disabled` wrapper relevan. Sumber: [OpenAI Docs](https://developers.openai.com/api/docs/models/gpt-4o-mini), [rilis DeepSeek V4.1-Flash](https://api-docs.deepseek.com/news/news260910/), dan [parameter thinking DeepSeek](https://api-docs.deepseek.com/guides/thinking_mode/).

**Rekomendasi reviewer tetap GPT-4o-mini untuk pilot pertama**, berdasarkan parameter yang lebih sederhana dan tarif standard yang diketahui. Ini pertimbangan integrasi, bukan klaim model tersebut pasti lebih cepat atau menghasilkan highlight lebih baik. DeepSeek non-thinking juga layak secara teknis; hasil daring yang menentukan kualitas dan waktu aktual. Tidak perlu memindahkan STT, mengubah chunking, atau mengganti framework untuk pilot ini.

## 5. Instruksi dan syarat eksekusi daring

### Sebelum mulai

1. Pengguna memilih salah satu profil: OpenAI `gpt-4o-mini`, atau DeepSeek `deepseek-flash` dengan thinking `disabled`. Tidak ada pergantian provider otomatis.
2. Pengguna menyetel kunci resmi secara lokal pada `OPENAI_OFFICIAL_API_KEY` atau `DEEPSEEK_API_KEY`. Pemeriksaan ketersediaan cukup berupa boolean; nilai kunci tidak diminta lewat chat dan tidak dicetak.
3. Gunakan endpoint bawaan; jangan memakai `--base-url`, `--api-key`, atau URL yang mengandung kredensial. Jangan menggunakan `--skip-render` untuk validasi end-to-end.
4. Sampaikan tarif yang dikoreksi, asumsi token, status biaya aktual belum terukur, dan batas yang benar-benar ditegakkan. Persetujuan lama untuk APMix tidak dianggap sebagai izin replay resmi baru.
5. Setelah izin satu replay diberikan, snapshot checksum 68 aset terproteksi dan berkas kode/harness yang relevan. Cadangkan summary global ke nama baru yang unik dan jangan menimpa backup terdahulu.
6. Jalankan proses runner terpisah dari server/interpreter lain agar monkey-patch guard tidak digunakan bersama pekerjaan lain. Pilih satu profil yang disetujui; jangan melakukan kedua provider sebagai percobaan otomatis.

### Selama dan sesudah replay

- Gunakan tepat satu invocation wrapper, sesi baru, nol STT Gemini, nol upload, dan maksimal empat inferensi highlight: satu klasifikasi/densitas dan tiga pemeringkatan chunk.
- Pertahankan retry SDK nol, fail-fast, request cap SDK 600 detik, budget job 1800 detik, serta cadangan 60 detik. Jangan menjalankan ulang otomatis ketika timeout/503/rate-limit terjadi.
- Simpan stdout/stderr, Job ID, metadata provider/model/mode, counter, waktu tahap yang benar-benar terukur, dan kandidat mentah per chunk sebelum deduplikasi. Biaya/usage yang tidak tersedia diberi label belum terukur.
- Bila menghasilkan klip, cocokkan metadata dengan file fisik, verifikasi durasi terhadap In/Out dan decode penuh media. Nilai ASS, VTT, framing, kualitas audio, dan sinkronisasi A/V terhadap sumber asli.
- Pisahkan pemilihan otomatis dari pengujian manual bagian akhir video. Catat kesiapan setiap klip: siap dipakai, edit ringan, edit besar, atau tidak layak.
- Periksa checksum kembali. Terbitkan laporan aktual walaupun run gagal; jangan menyatakan Video 3 selesai berdasarkan mock, status JSON, atau jumlah tes saja.

**Kriteria penutupan Video 3 end-to-end:** hasil replay nyata tersedia, bukti pemrosesan tiga chunk dapat diperiksa, klip fisik berhasil diverifikasi, kualitas audiovisual dinilai secara jujur, serta preservasi aset tetap utuh. Jika klip belum tersedia atau belum ditonton/didengar, penutupan belum dapat diberikan.

## 6. Inventaris bukti reviewer dan checksum

Semua hasil reviewer terisolasi pada `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`. Tidak ada panggilan API berbayar selama review ini.

- [Log 143 tes](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_closing_suite.log).
- [Hasil suite dan preservasi](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_closing_test_result.json).
- [Probe SDK, budget, context, dan URL](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_closing_probe_result.json).
- [Probe kedua urutan scheduler](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_official_closing_scheduler_probe_result.json).

| Berkas | SHA-256 yang terverifikasi |
| --- | --- |
| Harness asli | `033ac2a90a4b5b98ea1f519f47fa1d12bf5f85943b0cfdd984ee746d50b34f00` |
| Runner V3 | `3b5e4eef614327a7216bfb72a8cd212541b4bf18b830f75b42c8b3e0a6a306b1` |
| Media sumber V3 | `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` |
| Fixture STT | `5c0342f33294bd7ae605a76f0e169560c7fe1acfcc7bdd21de3f428aabffade5` |
| Wrapper terbaru | `9110edd6a80734de70956dc1c88d13c313d871f08600449f85e387700f059e5e` |
| Tes wrapper terbaru | `917d156da268a1f4f8133a6a80fc9471a9539eb3198bcc1ec21cfae1f30f8e67` |
| Tes editor terbaru | `0c322b32e36c27d75bf37b69cda70a4087e92bfaf5ba4107b9684925dba2fdcf` |

Perbandingan produksi menggunakan snapshot review sebelumnya, bukan klaim bahwa working tree identik dengan Git HEAD. Review ini hanya menambahkan dokumen dan artefak reviewer; tidak mengubah implementasi yang diaudit.
