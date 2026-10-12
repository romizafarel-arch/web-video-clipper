# Review independen — Controlled replay Video 3

Tanggal: 29 September 2026 (UTC+07:00).  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.  
Baseline: `main` / `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`.  
Job yang dilaporkan: `val_v3_replay_78278`.

## Keputusan

**Batas inferensi, blokade STT/upload, dan preservasi aset terkonfirmasi. Controlled replay gagal pada ranking Chunk 1; validasi end-to-end Video 3 belum selesai. Patch transkripsi tetap disahkan.**

Laporan belum dapat diterima sebagai bukti bahwa seluruh lifecycle, fail-fast, dan metadata replay otomatis sudah benar. Tiga koreksi terbatas di bawah diperlukan pada **harness replay baru dan pencatatan hasilnya**, sebelum mengulang request berbayar. Tidak ada permintaan membuka ulang Bagian A–C, Video 2, empat koreksi transkripsi, atau runner V3 asli yang sudah disahkan. Tidak diperlukan perubahan kode produksi.

## 1. Bukti yang diperiksa

- `docs/REVIEW_PATCH_TRANSKRIP_VIDEO_3_FINAL.md` dan laporan controlled replay.
- `scratch/run_controlled_replay_v3.py`, helper lifecycle/LLM/highlight yang dipanggilnya.
- Log sesi, JSON job dan `validation_v3_replay_summary.json`.
- Source/fixture dan snapshot checksum independen dari review penutup patch.
- Fungsi produksi dan orchestrator harness dieksekusi melalui AST kode aktual untuk probe offline. Dependency jaringan, probe media dan preflight pada simulasi orchestrator dimock; semua kemungkinan penulisan diarahkan ke folder sementara reviewer. JobManager/JobContext yang dipakai probe adalah implementasi produksi aktual. Tidak ada API berbayar atau modifikasi produksi/.env.

### Hasil verifikasi

| Butir | Hasil dan batas bukti |
| --- | --- |
| Inferensi highlight aktual | Log mengonfirmasi klasifikasi sukses, lalu ranking Chunk 1 menghasilkan `APITimeoutError`; tidak ada request Chunk 2/3 pada log. JSON mencatat dua dispatch, satu sukses dan satu gagal. Counter adalah bukti tingkat SDK, bukan billing export/server log. |
| Batas maksimum empat | Probe guard aktual: empat panggilan simulasi lolos, panggilan kelima ditolak sebelum mock dispatch. |
| STT/upload | Guard aktual menolak panggilan; alur replay membaca fixture langsung. Tidak ditemukan jalur STT/upload baru pada eksekusi yang dilaporkan. Tes guard sintetis dipisahkan dan counternya direset sebelum run. |
| Retry SDK | Inisialisasi OpenAI client aktual dengan patch harness menghasilkan `max_retries=0`. Tidak ada loop retry otomatis atau run kedua pada kode orchestrator. |
| Kandidat/render | Folder sesi hanya berisi log dan JSON job. Nol MP4/VTT dan tidak ada respons kandidat ranking yang berhasil. |
| Preservasi | **17 berkas V1 + 48 V2 + .env + source V3 + fixture = 68 berkas**, semuanya identik terhadap snapshot review sebelumnya. |
| Replay sanitizer independen | **5851 kata, 713 segmen, 3 estimated, 129 untrusted, 5 gap, kontrak valid**, input raw tidak berubah. |
| Kode produksi dan runner asli | Hash identik terhadap sign-off penutup. Harness replay baru merupakan berkas tambahan yang belum tercakup sign-off runner asli. |

Suite 122 unittest dan 21 guard sudah lulus pada review penutup sebelumnya, masing-masing 33,212s dan 8,367s. Kode produksi terkait tetap identik. Reviewer tidak mengulang discovery penuh yang sama pada audit ini; pengujian difokuskan pada harness baru yang tidak diimpor oleh suite 122 tes. Angka 34,584s pada laporan pelaksana tetap merupakan hasil yang dilaporkan pelaksana, bukan hasil pengukuran baru reviewer.

## 2. Koreksi terbatas

### V3-R01 — P1: Clock dan finalisasi lifecycle tidak aktif pada harness replay baru

Lokasi: `scratch/run_controlled_replay_v3.py:94`, `:107`, `:537`, `:559`, `:587`, `:695`, `:769`.

Harness memanggil `admit_job()` lalu `transition_to(RUNNING)`, tetapi tidak pernah mengisi `job_ctx.started_at`. `transition_to()` memang tidak mengisi field tersebut. Akibatnya:

- Request budget selalu jatuh ke default 300s.
- Pemeriksaan deadline melewati cabang timeout job karena `started_at` kosong. Konfigurasi `timeout_seconds=1800` tidak menjadi batas waktu aktif pada alur ini.

Tidak ada `try/except/finally` yang membungkus tahap klasifikasi/ranking/render. Dua blok try di orchestrator hanya menguji guard STT/upload. Saat ranking melempar exception, eksekusi keluar sebelum transisi terminal, penulisan metadata, log final, dan pemeriksaan preservasi pasca-run.

**Probe actual orchestrator dengan ranking timeout simulasi:** dua dispatch simulasi; status memori `running`, `error=null`, `started_at=null`, admission masih aktif dalam proses probe, **nol berkas job metadata dibuat**, dan pemeriksaan preservasi akhir tidak tercapai. Proses CLI asli memang berakhir, sehingga ini bukan klaim aplikasi web terus terkunci setelah proses tersebut mati.

Berkas job berstatus failed yang sekarang tersedia tidak dapat dihasilkan otomatis oleh jalur timeout pada kode harness ini. Ia perlu diberi asal pencatatan yang jelas sebagai rekonstruksi/pencatatan pasca-kegagalan, bukan bukti finalisasi otomatis berhasil.

**Koreksi minimum:** gunakan lifecycle worker yang sudah tersedia, atau isi clock sebelum dispatch pertama dan tambahkan finalisasi exception/finally pada harness ini. Bedakan timeout request upstream (`failed`) dari batas waktu job (`timeout`) dan pembatalan (`canceled`). Simpan status/error/counter/log/provenance serta checksum akhir pada jalur gagal juga. Uji ranking timeout dan deadline pendek secara offline; tidak diperlukan request berbayar untuk membuktikannya.

### V3-R02 — P1: Fail-fast belum berlaku jika klasifikasi pertama gagal

Lokasi: `scratch/run_controlled_replay_v3.py:567`, `:587`; perilaku helper di `shorts_generator/highlights.py:175`.

Pada run aktual, klasifikasi sukses dan error ranking menghentikan program. Untuk jalur tersebut, fail-fast dipatuhi. Namun `detect_content_type()` menangkap exception dan mengembalikan `other/medium`; harness tidak memeriksa bahwa klasifikasi gagal, sehingga tetap meminta ranking.

**Probe actual orchestrator:**

- SDK klasifikasi simulasi timeout pada dispatch pertama -> helper mengembalikan default -> **dispatch kedua tetap dilakukan**.
- SDK memberi teks bukan JSON pada klasifikasi pertama -> helper mengembalikan default -> **dispatch kedua tetap dilakukan**.

`max_retries=0` tidak mencegah dispatch berikutnya untuk tahap berbeda. Klaim umum "setiap kegagalan langsung menghentikan seluruh replay" belum benar pada harness baru ini.

**Koreksi minimum:** tegakkan klasifikasi yang gagal/invalid sebagai kegagalan replay di tingkat harness, tanpa mengubah helper produksi. Jangan memperlakukan default fallback sebagai respons klasifikasi berhasil. Tambahkan dua tes offline yang membuktikan hanya satu dispatch dilakukan ketika klasifikasi timeout atau JSON invalid, lalu status/metadata diselesaikan melalui finalisasi R01.

### V3-R03 — P2: Detail recovery dalam laporan/JSON tidak berasal dari hasil aktual

Lokasi: `docs/LAPORAN_CONTROLLED_REPLAY_VIDEO_3.md`, bagian 3.2/3.3; field `sanitization_summary` pada JSON job dan summary.

Source dan fixture tetap identik; sanitizer produksi juga identik dengan versi yang disahkan. Replay reviewer menghasilkan:

| Kata | Indeks raw aktual | Interval koreksi aktual | Laporan/JSON saat ini |
| --- | --- | --- | --- |
| hyper | 1228 | 512,600–513,267 | indeks 1226; 513,78–514,15 |
| arousal | 1229 | 513,267–513,933 | indeks 1227; 514,15–514,51 |
| hyper | 1230 | 513,933–514,600 | indeks 1228; 514,51–514,88 |

Jumlah kata per gap aktual adalah **57, 6, 2, 48, 16**; laporan/JSON berisi **57, 7, 1, 48, 16**. Totalnya sama-sama 129, sehingga pemeriksaan agregat tidak mengungkap ketidaksesuaian detail ini. Anchor 513,78/514,88 dalam narasi laporan juga tidak didukung replay fixture tersebut.

Eksklusi cluster 512,6–515,2 pada harness masih mencakup interval estimated aktual; karena tidak ada kandidat/render, tidak ada bukti klip salah telah diterbitkan. Masalah yang terbukti adalah integritas pencatatan.

Laporan menyebut replay "offline" secara umum, padahal hanya tahap sanitasi STT yang offline; klasifikasi/ranking memakai API daring. Durasi tahap yang tidak diinstrumentasi tidak boleh ditulis 0,00s sebagai hasil terukur. Log menyediakan elapsed klasifikasi sekitar 43,49s dan exception read timeout; waktu terminal mikrodetik, exact 300,00s, serta total wall time pada rekonstruksi perlu diberi sumber/label yang sesuai.

**Koreksi minimum:** hasilkan detail dari `recovery_audit`, `untrusted_spans`, hasil clock/counter, dan metadata runtime langsung. Koreksi laporan dan sediakan manifest koreksi yang jelas asalnya. Pertahankan log/fixture asli dan labeli rekonstruksi pasca-run; jangan menciptakan bukti historis yang seolah sudah ditulis otomatis oleh runner. Sertakan baseline dan hash harness/patch pada manifest berikutnya. Untuk fixture tetap ini, hardcoded estimated cluster sudah mencakup estimasi aktual, tetapi manifest tetap harus membuktikan kecocokannya terhadap audit.

## 3. Penilaian patch transkripsi

**Sign-off patch tetap berlaku.** Hash ketiga berkas produksi cocok dengan review penutup, dan replay independen sekali lagi memenuhi kontrak. Ketidaksesuaian indeks/timestamp dalam JSON tidak berasal dari perubahan sanitizer yang terbukti; ia berada pada pelaporan replay.

Yang terkonfirmasi adalah ketahanan struktural dan recovery terbatas pada fixture ini. Sinkronisasi terhadap audio tetap **Belum dinilai**. Nol klip berarti belum ada bukti decode hasil render, ASS/VTT, framing, A/V sync, atau kualitas editorial Video 3. Ini tidak membuka ulang empat koreksi transkripsi yang sudah selesai.

## 4. Penilaian timeout APMix

### Fakta

- Default request budget harness adalah 300s karena clock job kosong; diagnosis bagian ini benar dan direproduksi oleh probe.
- Log menunjukkan kegagalan ketika menerima header HTTP, berupa `httpcore2.ReadTimeout` -> `httpx2.ReadTimeout` -> `openai.APITimeoutError`.
- Chunk 1 mempunyai 340 baris teks transkrip, 20491 karakter dan 3122 item whitespace menurut fungsi produksi; ini bukan ukuran lengkap payload request yang juga memuat instruksi prompt.

### Hal yang belum terbukti

Log tidak menunjukkan durasi antrean atau komputasi internal APMix. Klaim bahwa model free-tier "memerlukan lebih dari 300s karena prompt besar" masih hipotesis. Gangguan proxy/jaringan atau provider juga tidak dapat dibedakan tanpa telemetry tambahan. Dua request belum membuktikan hubungan sebab-akibat antara panjang prompt dan latensi.

HTTPX memisahkan timeout connect/read/write/pool; read timeout membatasi waktu menunggu data pada operasi baca, sehingga menaikkan angka timeout tidak menetapkan deadline wall-clock total job. Implementasi lokal `httpx2`/`httpcore2` dalam traceback juga memakai timeout per operasi dan socket. Rujukan primer: [HTTPX — Timeouts](https://www.python-httpx.org/advanced/timeouts/).

## 5. Rekomendasi langkah berikutnya

**Opsi 3 terbatas terlebih dahulu:** selesaikan R01/R02 pada harness replay baru dan R03 pada pencatatan, dengan probe offline. Jangan mengulang STT, mengubah produksi, mengganti arsitektur, atau menjalankan API untuk menguji koreksi tersebut.

Setelah itu, **satu percobaan lanjutan dengan cap request 600s** merupakan eksperimen yang masuk akal bila pengguna masih ingin mempertahankan APMix. Angka ini rekomendasi percobaan, bukan jaminan keberhasilan atau bukti kebutuhan provider. Saya tidak menyarankan langsung menaikkan ke 900s.

- Isi clock job sebelum inferensi pertama.
- Terapkan timeout efektif `min(600s, sisa waktu job - cadangan)` dan tolak dispatch jika budget yang aman tidak tersisa. Seluruh request berbagi satu budget job 1800s; jangan memberi setiap chunk budget job baru.
- Pertahankan deadline/cancel kooperatif sebelum dan sesudah request serta pada exception. Jangan mengklaim hard cutoff persis 1800s hanya dari parameter SDK.
- Pertahankan 0 STT, 0 upload, maksimal 4 highlight, satu run, dan fail-fast. Izin run sebelumnya tidak otomatis mengizinkan run berbayar berikutnya.
- Jika tetap timeout, hentikan eksperimen memperpanjang timeout berulang. Provider/model highlight alternatif layak dipertimbangkan sesuai akses akun dan budget pengguna, dengan uji kompatibilitas singkat. Tidak ada bukti saat ini untuk menjamin model tertentu lebih cepat atau lebih murah.

Tiga ranking yang masing-masing menghabiskan 600s sudah mencapai 1800s sebelum klasifikasi/render; tiga kali 900s mencapai 2700s. Karena itu cap request dan budget job harus dipisahkan. Render/cleanup juga memerlukan waktu, dan cadangan 60s tetap parameter perencanaan yang belum dibuktikan cukup untuk hasil Video 3.

Keputusan operasional: **Video 3 belum ditutup; patch transkripsi tetap ditutup; lanjut hanya setelah tiga koreksi harness/pelaporan yang terbatas ini terbukti offline dan pengguna mengizinkan percobaan berikutnya.**

## 6. Artefak reviewer

Folder: `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`.

- `review_v3_replay_audit.py` / `.json`: replay produksi, perbandingan metadata, preservasi 68 file, guard cap/STT/upload, SDK max_retries, clock, dan tiga simulasi kegagalan orchestrator.
- `review_v3_closing_full_before.json`: referensi checksum dari sign-off penutup untuk pembandingan preservasi.

SHA-256 harness replay yang diperiksa: `ce6aaa3148ce99830f5cc048f65e33198ac893f51f352d88022f0638ef50cf49`.

Fingerprint produksi tetap:
- Gemini adapter: `6cc4ba155524eb84d6528cacc61a1663f1e0f127190bb3cc10f30ac0570f23f5`.
- Transcriber/cache: `7e5fb652d6acd9e9cbfda823520fad2bb4063f3dec735782f3e10890a181f5ca`.
- Highlights: `2d2f77400bd6ae5acb807c0454e40611d4a3b29520d75adc982699e97500b1e0`.
