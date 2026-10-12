# Review independen Bagian B — ShortsStudio

Tanggal: 28 September 2026.

Checkout yang diperiksa: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.
Branch: `main`; HEAD: `de07f3a94a9ef0c4c55376cfa118141de62a3d43`.
Perubahan Bagian A dan B berada di working tree lokal; HEAD bukan representasi seluruh kode yang diperiksa.

## Keputusan

**Bagian B belum dapat disahkan selesai.** Modul job manager, penguncian admission, pembatalan manual FFmpeg pada konteks running, dan pembacaan status terminal dari disk merupakan kemajuan yang benar. Namun, jalur produksi untuk timeout, persistensi sebelum selesai, penghapusan bersamaan dengan editor, dan pemulihan UI belum memenuhi kontrak yang diminta.

Ini tidak membuka kembali kriteria editor Bagian A. Temuan berikut dibatasi pada enam kriteria Bagian B dan mutu bukti pengujiannya. Tidak diperlukan migrasi framework, database, atau scheduler baru.

## Verifikasi independen

- Semua **41 tes baseline Bagian A lulus**, termasuk render FFmpeg nyata.
- Suite lengkap 52 tes tersangkut pada `tests/test_job_lifecycle.py:203`, yaitu `worker_started.wait()` tanpa timeout. Pengulangan dengan diagnosis thread mengonfirmasi lokasi tunggu tersebut.
- Dengan satu tes concurrency yang mencemari fungsi global dipisahkan, **51/51 tes lulus**, 6,178 detik, tanpa error, failure, atau skip.
- Assertion tes concurrency juga lulus ketika dijalankan terpisah dengan interleaving yang dikendalikan, tetapi meninggalkan `web_app.run_generation_job` sebagai `MagicMock`. Artinya, keberhasilan assertion tersebut tidak membuktikan suite aman dijalankan penuh.
- Probe tambahan menjalankan kode worker dan crop loop sebenarnya dengan input/layanan eksternal yang disimulasikan, memakai direktori sementara.
- Probe deadline menggunakan **FFmpeg nyata** dengan input sintetis real-time. Timeout 0,2 detik belum memicu penghentian setelah 0,825 detik. Pembatalan manual konteks running berhasil menghentikan proses yang sama dalam sekitar 0,015 detik; registry kembali kosong.
- Pemeriksaan frontend menjalankan fungsi `startPolling` dan `resumeActiveJobIfAny` yang diekstrak langsung dari `static/js/app.js`, menggunakan Node VM dan stub DOM/network. Ini pemeriksaan kontrak state, **bukan pengujian visual browser nyata**.
- Runner browser yang dilaporkan (`tests/browser_qa.js`, `tests/run_browser_qa.py`) masih menguji editor Bagian A. Tidak ditemukan skenario generate/cancel/resume/network recovery untuk lifecycle Bagian B di runner tersebut. Screenshot modal editor tidak membuktikan kontrol pembatalan job atau pemulihan lifecycle.

Sandbox awal memblokir eksekusi FFmpeg. Verifikasi kemudian dijalankan dengan izin eksekusi lokal yang disetujui, memakai binary FFmpeg terpasang. Kegagalan izin awal tidak dihitung sebagai bug aplikasi. Tidak ada panggilan API berbayar selama review.

## B-01 — P1: deadline tidak menghentikan FFmpeg yang masih berjalan

Lokasi:
- [local/clipper.py:183](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/clipper.py:183)
- [job_manager.py:190](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/job_manager.py:190)

`_run_ffmpeg_cmd` memeriksa deadline sebelum membuat proses, lalu memanggil `proc.wait()` tanpa timeout. Selama proses berjalan tidak ada checkpoint. Sesudah exit sukses pun deadline tidak diperiksa di helper ini. Tidak ada watchdog terpisah yang mengaktifkan deadline ketika worker terblokir di sini.

Bukti: FFmpeg real-time masih hidup, status tetap `running`, dan `cancel_event=False` setelah 0,825 detik pada batas 0,2 detik. Proses akhirnya dihentikan oleh pembatalan manual untuk membersihkan fixture.

Perbaikan minimum: gunakan penantian proses berbatas pendek dengan pemeriksaan cancellation/deadline di antara interval, lalu terminate/kill dan wait sampai exit. Untuk tahap kooperatif yang tidak bisa diputus langsung, permintaan timeout harus tetap terlihat sebagai penghentian yang sedang berlangsung dan admission tidak dilepas sebelum worker selesai. Gunakan batas tunggu eksplisit untuk operasi eksternal yang mendukungnya. Kebijakan total 1800 detik perlu dinyatakan sebagai batas total yang dapat diatur, bukan deteksi otomatis bahwa proses macet.

Tes penutup: FFmpeg real-time yang lebih panjang daripada deadline harus berhenti tanpa polling HTTP atau pembatalan manual, dan job baru tetap ditolak hingga cleanup selesai.

## B-02 — P1: boot recovery tidak memiliki catatan job aktif dari jalur produksi

Lokasi:
- [web_app.py:297](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:297)
- [web_app.py:436](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:436)
- [job_manager.py:327](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/job_manager.py:327)

Metadata baru ditulis dalam `finally`, setelah pipeline keluar. Job queued yang dibatalkan juga langsung return sebelum blok penyimpanan. Karena itu, crash saat download/transcribe/analyze/crop biasanya meninggalkan folder tanpa `job_<id>.json`; startup scanner tidak punya catatan untuk ditandai `interrupted`.

Bukti: saat worker nyata ditahan di dalam tahap pipeline, folder sesi berisi **0 metadata job**, dan recovery mendapatkan **0 job**. Tes recovery repository membuat sendiri JSON berstatus running, sehingga tidak memverifikasi bahwa aplikasi benar-benar menghasilkan record tersebut.

Perbaikan minimum: buat identitas sesi dan catatan awal saat admission/before execution, lalu simpan perubahan lifecycle penting secara atomik di bawah session lock. Persistensikan queued cancellation dan alasan penghentian juga. Pertahankan hasil/source/transcript yang tersedia tanpa menimpa revisi editorial dengan snapshot lama. Kegagalan penyimpanan harus terlihat jelas; jangan mengklaim pemulihan tersedia ketika catatannya gagal ditulis.

Tes penutup: jalankan jalur generate produksi dengan layanan simulasi, pastikan metadata aktif sudah ada sebelum selesai, lalu simulasikan proses aplikasi baru membaca disk dan mendapatkan `interrupted` tanpa memanggil AI lagi.

## B-03 — P1: pemeriksaan lock sebelum delete masih memiliki celah waktu

Lokasi:
- [web_app.py:1311](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:1311)
- [web_app.py:1460](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:1460)

Delete memegang session lock, mencoba clip lock, lalu langsung melepas clip lock sebelum menghapus. Editor dapat mengambil clip lock sesudah pemeriksaan itu dan memulai render sebelum delete selesai. Editor hanya mengambil session lock untuk tahap commit; render sebelumnya masih dapat berlangsung sementara foldernya dihapus.

Bukti interleaving terkontrol: delete berhenti tepat setelah pemeriksaan lock; editor mulai render; delete dilanjutkan. Hasilnya **DELETE 200**, folder lama sudah hilang saat render berlangsung, dan editor mendapat **500**.

Perbaikan minimum: koordinasikan pendaftaran operasi editor/generasi dan keputusan penghapusan memakai gerbang sesi yang sama. Penghapusan harus menolak operasi aktif, atau operasi edit yang kalah terhadap delete harus ditolak sebelum render. Pemeriksaan lock sesaat tidak cukup. Tetap pertahankan kemampuan render klip berbeda secara paralel dari Bagian A; jangan mengunci seluruh proses render semua klip hanya untuk memudahkan delete.

Tes penutup: paksa interleaving seperti di atas. Hasil lama harus tetap ada jika editor telah aktif; atau editor ditolak dengan respons jelas sebelum render jika delete lebih dahulu mendapat hak operasi.

## B-04 — P2: hasil kosong dan penyebab timeout masih salah diklasifikasikan

Lokasi:
- [web_app.py:364](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:364)
- [local/clipper.py:437](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/clipper.py:437)
- [job_manager.py:192](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/job_manager.py:192)
- [job_manager.py:226](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/job_manager.py:226)

Kondisi failed mensyaratkan `len(shorts)>0`. Jika pipeline mengembalikan `shorts=[]`, worker justru memilih `completed`. Tes bernama zero-clips hanya memakai daftar tidak kosong yang seluruh `clip_url`-nya None, sehingga melewatkan daftar kosong.

Selain itu, crop loop menelan exception cancellation/timeout dan mengembalikan daftar hasil. Transisi dari canceling ke completed selalu dipetakan menjadi partial/canceled tanpa mempertahankan jenis penghentian. `cancel_event` yang sudah aktif juga selalu menghasilkan `JobCancelledException` pada checkpoint berikutnya meskipun awalnya disebabkan timeout.

Bukti:
- `{"shorts": []}` tanpa pembatalan menghasilkan **completed**, seharusnya failed.
- Timeout yang dilempar di dalam render klip menghasilkan **canceled**, dengan alasan timeout.

Perbaikan minimum: simpan penyebab penghentian secara terstruktur dan pertahankan ketika exception dibawa naik atau hasil parsial diteruskan. Partial karena timeout boleh tetap bernama partial, tetapi harus membawa alasan timeout dan klip sukses yang lengkap. Nol sukses tanpa pembatalan harus failed. Jangan mengubah exception penghentian menjadi completed atau kehilangan metadata hasil parsial.

Tes penutup: hasil benar-benar kosong, cancel sebelum klip pertama, timeout saat klip pertama, serta cancel/timeout sesudah satu klip sukses harus memiliki status/alasan/hasil yang konsisten di memory dan disk.

## B-05 — P1: propagasi cancellation belum mencakup jalur API dan beberapa operasi lokal

Lokasi:
- [pipeline.py:110](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/pipeline.py:110)
- [pipeline.py:199](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/pipeline.py:199)
- [local/gemini_transcriber.py:56](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:56)
- [local/gemini_transcriber.py:81](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:81)

`generate_shorts(... mode='api')` tidak meneruskan job context ke `_run_api`, dan `_run_api` tidak melakukan checkpoint. Pembatalan dapat tetap diikuti transkripsi, analisis, dan crop remote berikutnya. Penguncian admission mencegah job baru, tetapi tidak menghentikan pekerjaan yang sudah tidak diinginkan.

Bukti offline: cancellation dipicu oleh mock download API. Setelah itu **transcribe dan crop tetap dipanggil**. Tidak ada layanan nyata atau biaya API yang digunakan untuk membuktikannya.

Pada mode lokal, ekstraksi audio Gemini masih memakai FFmpeg `subprocess.run` tanpa registrasi job/deadline. Downloader dan Gemini processing loop juga tidak menerima konteks job; pembatalan hanya dilihat setelah tahap selesai. Keterbatasan pembatalan call yang sudah berlangsung boleh didokumentasikan, tetapi tidak membenarkan memulai tahap berikutnya setelah stop diminta atau menunggu loop polling tanpa batas yang dikendalikan aplikasi.

Perbaikan minimum: teruskan konteks ke jalur API, periksa sebelum tahap/call berikutnya serta pada loop polling, dan gunakan tracking proses bersama untuk FFmpeg ekstraksi audio. Terapkan finite timeout pada call/loop yang mendukungnya. Tidak perlu menambahkan hard-kill thread atau mengklaim pembatalan remote provider jika API provider tidak mendukungnya.

Tes penutup: layanan remote disimulasikan; stop di tahap pertama harus mencegah tahap lanjutan. Uji juga satu FFmpeg ekstraksi audio yang diregistrasikan serta loop processing yang berhenti pada stop/deadline. Jika mode API sengaja di luar dukungan lifecycle, nonaktifkan aksesnya secara eksplisit dan dokumentasikan batas tersebut; jangan mengiklankan kontrak yang sama ketika UI masih mengizinkannya.

## B-06 — P2: pemulihan UI tidak menangani seluruh kontrak terminal

Lokasi:
- [web_app.py:1039](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:1039)
- [static/js/app.js:827](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/static/js/app.js:827)
- [static/js/app.js:857](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/static/js/app.js:857)
- [static/js/app.js:1914](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/static/js/app.js:1914)

Empat jalur terbukti dari fungsi JS sebenarnya:
1. `interrupted` tidak memiliki handler terminal: polling dan key aktif tidak dibersihkan.
2. Respons disk mengirim logs sebagai array, sedangkan frontend memanggil `job.logs.toLowerCase()`. Pada animation view, exception terjadi sebelum handler terminal sehingga failure dibaca sebagai gangguan polling.
3. Refresh dengan saved job yang sudah partial menghapus key tanpa menampilkan hasil parsial/pesan. Jalur resume hanya merender completed.
4. Jika request pertama saat resume gagal karena jaringan, fungsi berhenti tanpa menjadwalkan retry. Halaman tidak otomatis melanjutkan pemantauan ketika jaringan kembali.

Perbaikan minimum: seragamkan schema API (logs string), gunakan penanganan state yang sama saat polling maupun resume termasuk interrupted dan partial, serta retry pemulihan awal setelah kegagalan sementara. 404 perlu pesan jelas sebelum key dibersihkan. Respons gagal endpoint cancel juga harus diperlakukan sebagai kegagalan permintaan agar tombol tidak terjebak disabled.

Tes penutup: browser nyata melakukan refresh/reconnect, menerima interrupted dan partial, gagal pada request resume pertama lalu pulih, dan membaca respons disk. Periksa tombol pembatalan pada desktop/390/320 dan keyboard, bukan hanya modal editor.

## B-07 — P2: suite tidak stabil dan bukti browser belum menguji Bagian B

Lokasi:
- [tests/test_job_lifecycle.py:235](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/test_job_lifecycle.py:235)
- [tests/test_job_lifecycle.py:203](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/test_job_lifecycle.py:203)
- [tests/test_job_lifecycle.py:369](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/test_job_lifecycle.py:369)
- [tests/browser_qa.js:1](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/tests/browser_qa.js:1)

Tes dua request membuka `patch('web_app.run_generation_job')` masing-masing di dua thread. Jika dua konteks patch tumpang tindih lalu keluar dengan urutan yang sama seperti masuk, fungsi global tertinggal sebagai MagicMock. Tes berikutnya memulai mock sebagai worker sehingga event pipeline tidak pernah disetel. Diagnosis thread suite menunjukkan main thread menunggu event tanpa batas.

Probe memaksakan urutan tersebut tanpa mengubah kode sumber: assertion 200/409 lulus, tetapi `ORIGINAL_WORKER_RESTORED=False` dan tipe fungsi sesudah tes adalah `MagicMock`.

Tes FFmpeg yang dilaporkan memakai konteks queued; `request_cancel` queued tidak memanggil terminate_all. Proses stream-copy juga dapat sudah selesai sebelum assertion. Tes itu belum menjamin penghentian proses yang masih hidup. Pengujian nyata review memakai konteks running, memastikan proses terdaftar/hidup sebelum cancel, dan mengukur waktu stop.

Perbaikan minimum: pasang patch sekali di thread pengujian utama, gunakan client per thread, buat semua waits/joins berbatas dan pastikan cleanup thread. Tambahkan kasus produksi yang dibuktikan dalam B-01 s/d B-06, serta skenario browser lifecycle. Keberhasilan runner editor Bagian A tetap merupakan bukti regresi editor, tidak perlu dibuang atau diganti namanya menjadi bukti lifecycle penuh.

Tes penutup: jalankan suite lengkap tanpa menggantung, tanpa skip untuk integrasi lokal yang tersedia, dan pastikan fungsi worker asli dipulihkan setelah tes concurrency.

## Matriks enam kriteria yang disepakati

| Kriteria | Penilaian | Penutupan yang diperlukan |
|---|---|---|
| 1. Status dan admission tunggal | Sebagian besar sesuai; hasil kosong/penyebab stop belum benar | B-04 dan regresi B-07 |
| 2. Pembatalan nyata | Manual FFmpeg running terbukti; propagasi belum menyeluruh | B-05; retensi/alasan B-04 |
| 3. Timeout | Belum memenuhi ketika FFmpeg menunggu | B-01, B-04, B-05 |
| 4. Persistensi dan pemulihan | Pembacaan terminal ada, record aktif sebelum crash belum ada | B-02 |
| 5. Ketahanan UI | Happy path ada, recovery terminal/network belum lengkap | B-06, bukti browser B-07 |
| 6. Perlindungan penghapusan sesi | Menolak aktivitas yang sudah terlihat; race tetap menghapus hasil | B-03 |

## Batas penutupan

Perbaiki B-01 s/d B-07 saja; pertahankan 41 regresi Bagian A. Setelah tes produksi yang terarah, suite lengkap stabil, dan QA browser lifecycle lulus, Bagian B dapat direview untuk penutupan. Jangan mulai Bagian C, NVENC, tracking, integrasi ekspor, atau redesign.

Tidak diperlukan transaksi filesystem tahan mati daya, hard-kill thread Python, atau sistem antrean terdistribusi. Keterbatasan kooperatif boleh dipertahankan dengan status jujur, stop signal yang benar, dan batas tunggu yang dijelaskan.

Artefak reproduksi di folder laporan:
- `review_b_probes.py`: worker/crop/persistence/delete/API dan FFmpeg nyata.
- `review_b_frontend.cjs`: fungsi polling/resume asli dengan DOM/network stub.
- `review_b_test_patch_race.py`: interleaving patch tes concurrency.

Kode aplikasi, konfigurasi, dan media asli tidak diubah dalam review. Probe independen membersihkan fixture serta proses FFmpeg miliknya. Dua eksekusi suite yang tersangkut telah dihentikan; direktori sementara dari suite yang terinterupsi mungkin masih tertinggal di Temp. Hanya laporan dan probe independen disimpan di folder visualizations.
