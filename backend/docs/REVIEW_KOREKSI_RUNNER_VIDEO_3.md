# Review Penutup Koreksi Runner Video 3 — ShortsStudio

Tanggal: 29 September 2026, UTC+07:00.

Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.

HEAD: `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`, branch `main`. Runner dan tes Video 3 masih untracked; dokumen rencana memiliki perubahan lokal. Tidak ada diff pada kode produksi `shorts_generator/` atau `web_app.py`.

## 1. Keputusan

**V3-02 disahkan selesai untuk pemetaan klip hilang, urutan acak, dan berkas tanpa completion record.** Perbaikan inti V3-01 pada request inferensi juga sudah benar: timeout sesuai satuan, pemeriksaan sebelum/sesudah request, propagasi cancel/deadline, dan pembedaan error jaringan.

**Sign-off penuh runner belum diberikan karena dua residu pada penghentian/cleanup V3-01.** Keduanya terbatas pada harness: cleanup hasil upload yang kembali bersamaan dengan stop dan finalisasi summary ketika worker belum berhenti setelah join terbatas. Tidak diperlukan perubahan arsitektur atau pembukaan ulang Bagian A–C maupun Video 2.

Pemilihan sumber serta penetapan bahasa, model/provider, dan kuota Video 3 boleh berlangsung sekarang. Cold run berbayar menunggu dua koreksi tersebut serta persetujuan parameter pengguna.

## 2. Hasil verifikasi independen

| Pemeriksaan | Hasil |
| --- | --- |
| Suite guard dijalankan ulang | **15 tes, 5,273 detik, OK**, exit code 0 |
| Cancel selama inferensi OpenAI/Gemini | Kedua wrapper mengangkat `JobCancelledException`, success tidak bertambah |
| Deadline selama inferensi OpenAI/Gemini | Kedua wrapper mengangkat `JobTimeoutException` |
| Timeout jaringan sebelum deadline job | Tetap `TimeoutError` pada fixture, tidak dipaksa menjadi timeout job |
| Timeout SDK dalam probe terkendali | OpenAI 1740 detik; Gemini 1740000 milidetik |
| Eksekusi fungsi runner dengan manifest [#3, #2] | #2 mendapat judul dan selection durasi 8 detik; #3 mendapat miliknya, durasi 12 detik |
| Berkas #1 tanpa completion record | completion_record_found dan verified_complete keduanya false |
| Cancel ketika polling | Upload 1, get 1, delete 1, generate 0; timeout cleanup 15000 ms |
| Cancel/timeout ketika upload selesai | Exception stop benar, tetapi **delete 0**; rincian pada residu pertama |
| Worker tetap hidup setelah join | **TypeError: Object of type JobContext is not JSON serializable**; pointer summary tidak tersimpan |
| Preservasi referensi Video 1–2 | **10/10 artefak identik SHA-256** dengan bukti review terdahulu |

Suite 108 tes tidak dijalankan ulang auditor pada tahap ini: kode produksi tidak berubah dan sebelumnya sudah diverifikasi independen. Angka 108 tes/34,498 detik pada laporan merupakan bukti pelaksana, bukan pengukuran baru auditor.

Probe independen mengeksekusi fungsi AST kode terkini, termasuk fungsi produksi `transcribe_with_gemini` bersama wrapper File API dari runner. Dispatch SDK, probe/decode media, dan kondisi worker tertentu diganti fixture offline. Jaringan diblokir pada probe. Bukti ini menguji alur kontrol dan pemetaan metadata; tidak mengklaim unggah/penghapusan server atau decode media baru yang nyata. Tidak ada panggilan API berbayar atau pengunduhan media oleh auditor.

## 3. Residu V3-01.a — P2: File upload yang telah diketahui tidak dibersihkan saat post-check menghentikan jalur

Lokasi: [hasil upload dan checkpoint sesudahnya](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:306), dengan caller [assignment uploaded_file](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:542).

Wrapper menerima objek File dari `_orig_files_upload`, lalu menjalankan post-check. Bila cancel/timeout terjadi selama upload, post-check melempar exception sebelum objek File dikembalikan kepada caller. Pada kode produksi, assignment `uploaded_file = client.files.upload(...)` berada sebelum blok try/finally cleanup. Akibatnya caller belum memiliki File ID dan belum masuk blok finally. Wrapper juga tidak membersihkan objek yang sudah diterimanya.

Bukti integrasi offline:

| Skenario | Exception keluar | Upload | Delete | Inferensi |
| --- | --- | --- | --- | --- |
| Cancel selama upload, SDK mengembalikan File bernama | JobCancelledException | 1 | **0** | 0 |
| Deadline habis selama upload, SDK mengembalikan File bernama | JobTimeoutException | 1 | **0** | 0 |
| Cancel saat polling, sesudah upload masuk try/finally | JobCancelledException | 1 | **1** | 0 |

Jadi tes ke-15 membuktikan bahwa delete dapat dipanggil pada job canceled, tetapi belum membuktikan delete benar-benar dipanggil pada batas upload/caller ini.

Perbaikan minimal tetap di harness: jika post-check upload mengangkat exception kontrol setelah menerima File bernama, upayakan delete terhadap File tersebut menggunakan wrapper cleanup 15 detik, catat hasilnya, lalu teruskan exception cancel/timeout asli. Kegagalan delete tidak boleh mengganti exception kontrol atau memicu inferensi/fallback. Hindari double delete pada jalur upload normal.

Tambahkan tes integrasi cancel dan timeout selama upload melalui caller transkripsi yang nyata, dengan transport upload/delete dimock. Harapkan upload 1, delete 1, generate 0, serta exception kontrol yang benar. Sertakan delete gagal untuk membuktikan exception utama tetap dipertahankan dan kegagalan cleanup tercatat.

Perbaikan ini hanya menjanjikan upaya cleanup ketika File ID sudah diketahui. Jangan mengklaim jaminan penghapusan server ketika jaringan gagal sebelum SDK mengembalikan identitas file.

## 4. Residu V3-01.b — P2: Jalur worker masih hidup setelah join tidak menghasilkan laporan yang aman

Lokasi: [join terbatas](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:663), [objek aktif dalam summary](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:851), dan [serialisasi JSON](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:875).

`thread.join(timeout=1860.0)` tidak menghentikan worker dan dapat kembali ketika thread masih hidup. Runner kemudian meneruskan verifikasi media, mengambil JobContext aktif, serta memasukkan objek tersebut langsung ke summary. `json.dumps` tidak dapat menyerialisasikan JobContext.

Probe memakai thread fixture yang menyatakan masih hidup setelah join, tanpa menunggu 1860 detik dan tanpa thread macet nyata. Fungsi eksekusi runner menghasilkan TypeError tersebut; pointer summary tidak ditulis. Karena itu penambahan batas join belum disertai penanganan jalur ketika batas tersebut tercapai.

Pilih solusi terkecil sesuai kebutuhan runner:

- Jika outer wait terbatas tidak diperlukan, pertahankan penantian sampai worker benar-benar selesai, mengandalkan timeout request dan checkpoint kooperatif yang sudah dipasang.
- Jika join terbatas dipertahankan, tangani `worker_thread_alive` sebelum verifikasi final: upayakan penghentian kooperatif, laporkan keadaan masih berjalan/tidak selesai secara jujur, dan simpan hanya nilai serializable yang sudah disanitasi, misalnya Job ID/status. Jangan menandai job terminal atau media sebagai final ketika worker masih memutasi artefak. Akhiri jalur tersebut dengan pelaporan eksplisit, bukan TypeError.

Tidak perlu menambah process supervisor atau mengklaim hard kill. Tambahkan satu tes jalur worker masih hidup jika memilih opsi join terbatas. Bukti lulusnya harus mencakup summary serializable, status belum selesai yang jujur, dan tidak adanya verifikasi/promotion final prematur.

## 5. Penilaian V3-02 dan perapian dokumentasi

Lookup berbasis index/filename menutup masalah posisi list. Probe fungsi eksekusi terkini mengonfirmasi hasil parsial teracak dan orphan ditangani benar. V3-02 tidak perlu dibuka ulang untuk dua residu cleanup/finalisasi di atas.

Tes ke-13 saat ini membangun ulang lookup di dalam tes, sehingga belum menguji fungsi runner secara langsung. Ini catatan kekuatan regresi, bukan penghalang penutupan V3-02 pada kode terkini karena probe auditor telah menguji fungsi runner. Saat merapikan suite, utamakan pengujian fungsi yang benar-benar dipakai runner.

Counter polling, label cadangan 60 detik sebagai parameter perencanaan, sifat timeout kooperatif, peak RAM belum terukur, kandidat relatif sesudah sanitasi, dan syarat keberadaan segmen untuk tiga chunk sudah diperjelas secara memadai. Detail kecil tabel durasi masih menggunakan kata “menjamin”; selaraskan dengan catatan bersyarat tanpa menambah tahap audit.

Luruskan dua klaim pada laporan pelaksana saat mengerjakan koreksi yang sama:

1. Cleanup adalah **upaya dengan hasil dicatat**, bukan jaminan pembersihan staging; residu upload dan error delete menjelaskan batasnya.
2. “Setiap kegagalan jaringan atau parsing menghentikan run seketika” terlalu luas. [detect_content_type](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/highlights.py:175) masih menangkap Exception dan memakai klasifikasi other/medium. Jelaskan bahwa fail-fast yang terbukti mencakup ranking serta larangan retry/dispatch tambahan sesuai guard; jangan mengubah perilaku produksi hanya untuk menyelaraskan klaim.

Field `verified_complete` sekarang menggabungkan adanya record dan decode_success. Penilaian QA keseluruhan tetap harus membaca duration_within_tolerance serta hasil pemeriksaan subtitle secara terpisah; field tersebut tidak membuktikan kesiapan publikasi atau keseluruhan mutu media.

## 6. Batas tindak lanjut

Tutup dua residu V3-01 di harness dan tes offline terkait. Pertahankan V3-02 sebagai selesai, cap API, baseline A–C, dan artefak terdahulu. Tidak perlu mengulang seluruh suite 108 tes atau browser QA jika produksi tidak diubah.

Setelah dua jalur itu terbukti benar dan pengguna menyetujui sumber, bahasa, provider/model, serta kuota, lanjutkan satu cold run Video 3. Tidak ada eksekusi berbayar atau pengulangan otomatis yang disahkan oleh review ini.

## 7. Inventaris bukti

- [Log 15 tes guard](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_closing_guard_suite.txt).
- [Hasil probe integrasi dan pemetaan](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_correction_probes.json).
- [Skrip probe offline](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_correction_probes.py).

SHA-256 runner yang diperiksa: `2972C2731DE9AB91D5F7109642C68F6B307866B52AFD8A0B4259763053A4E10B`.

SHA-256 suite guard yang diperiksa: `BDC108EC650F7E1E357045164B0E895C84D2590B5A9B5F856F49EC68147EEB7B`.
