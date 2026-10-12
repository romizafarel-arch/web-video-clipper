# Review Independen Persiapan Video 3 — ShortsStudio

Tanggal: 29 September 2026, UTC+07:00.

Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.

HEAD: `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`, branch `main`.

## Keputusan

**Pemilihan dan penetapan sumber Video 3 boleh dilanjutkan sekarang. Sign-off penuh runner untuk cold run berbayar ditunda sampai dua koreksi terbatas V3-01 dan V3-02 selesai.** Koreksi ini berada pada harness validasi, bukan alasan membuka ulang Bagian A–C atau penutupan teknis Video 2.

Guard kuota, override retry ranking, isolasi output, dan simulasi chunking sudah bekerja pada kasus yang diuji. Delapan tes offline lulus ketika auditor menjalankannya ulang. Akan tetapi, suite tersebut belum menguji request yang sedang berjalan saat cancel/deadline terjadi, maupun pemetaan metadata hasil parsial dengan nomor klip yang tidak berurutan.

Tidak ada kode produksi yang diubah auditor, API nyata yang dipanggil, atau media yang diunduh dalam review ini. Kode produksi juga tidak memiliki diff terhadap HEAD saat pemeriksaan.

## 1. V3-01 — P1: Kontrol deadline hanya sebelum dispatch; request belum dibatasi sesuai sisa waktu

Lokasi: [wrapper OpenAI](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:108), [wrapper Gemini](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:132), dan [penantian worker](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:496).

Kedua wrapper hanya memanggil `_check_deadline_before_dispatch` sebelum masuk SDK. Keduanya tidak memasang timeout request berdasarkan sisa waktu dan langsung mengembalikan respons setelah SDK selesai. `thread.join()` juga menunggu tanpa batas tersendiri.

Pemeriksaan lokal SDK menunjukkan OpenAI memakai timeout bawaan `connect=5s`, `read/write/pool=600s`, sedangkan Gemini tanpa `HttpOptions.timeout` memiliki timeout `None`. Nilai tersebut tidak dikaitkan dengan deadline job. Cadangan 60 detik hanya merupakan syarat boleh memulai request; syarat itu tidak menyediakan cadangan apabila request berikutnya menunggu terlalu lama.

**Bukti offline:** probe dimulai dengan sisa waktu 100 detik, lalu mock SDK memajukan waktu 120 detik sebelum mengembalikan respons. Pada kedua provider, wrapper mengembalikan respons tanpa exception meskipun deadline sudah lewat 20 detik. Probe cancel selama mock SDK juga mengembalikan respons tanpa meneruskan cancel pada saat wrapper kembali. Ini membuktikan kekurangan wrapper, bukan klaim bahwa worker produksi pasti berakhir `completed`: checkpoint berikutnya pada pipeline masih dapat menangkap kondisi stop. Namun worker tidak dapat mencapai checkpoint itu selama SDK masih menggantung.

Perbaikan minimal, hanya dalam proses harness:

- Hitung anggaran request dari sisa deadline dikurangi cadangan. Teruskan timeout terbatas melalui mekanisme SDK yang sesuai; satuan Google `HttpOptions.timeout` adalah milidetik, sedangkan timeout OpenAI menggunakan detik.
- Periksa cancellation/deadline sesudah SDK kembali dan ketika SDK melempar exception. Jika deadline job habis, teruskan `JobTimeoutException`; jika cancel aktif, teruskan `JobCancelledException`. Timeout jaringan sebelum deadline habis dapat tetap dilaporkan sebagai kegagalan jaringan, bukan dipaksakan menjadi timeout job.
- Batasi juga operasi upload/poll/delete Gemini agar fase File API tidak menjadi penantian tanpa batas. Cleanup tetap diupayakan dengan timeout tersendiri yang terbatas, termasuk saat job sudah canceled.
- Tambahkan tes offline pada wrapper nyata: cancel selama request, deadline selama request, serta bukti parameter timeout benar-benar diteruskan ke SDK. Pertahankan cap dan larangan retry.

Tidak diperlukan supervisor proses, antrean baru, atau parallel ranking untuk menutup temuan ini. Timeout jaringan dan checkpoint tetap bukan jaminan penghentian keras tepat pada detik 1800. Cadangan 60 detik perlu diberi label parameter perencanaan; kecukupannya untuk render/cleanup belum dibuktikan.

## 2. V3-02 — P2: Verifikasi media memasangkan metadata berdasarkan posisi list

Lokasi: [pemilihan metadata klip](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:614).

Loop memeriksa `short_01.mp4` sampai `short_03.mp4`, tetapi mengambil metadata dengan `result_shorts[i - 1]`. Ketika salah satu render gagal atau list hasil tidak berurutan, posisi list tidak lagi sama dengan nomor klip. Akibatnya summary dapat melaporkan judul, In/Out, dan deviasi durasi milik klip lain.

**Bukti offline pada fungsi eksekusi runner:** worker fixture menghasilkan status partial dengan dua completion record, klip #2 dan #3. Media probe/decode diganti mock; ini merupakan tes pemetaan data, bukan tes media fisik.

| Berkas | Durasi fixture sebenarnya | Metadata yang dipakai runner |
| --- | --- | --- |
| `short_02.mp4` | 8 detik; selection 10–18 | Judul klip #3; selection 20–32; expected 12 detik; mismatch palsu |
| `short_03.mp4` | 12 detik; selection 20–32 | Expected duration dan judul tidak terisi |

Perbaikan minimal: petakan completion record menggunakan `clip_index` atau filename kanonikal, lalu cocokkan setiap berkas dengan record miliknya. Jangan mengandalkan urutan list. Tetap bedakan berkas yang tidak memiliki completion record dari klip terverifikasi.

Tambahkan satu tes hasil parsial dengan nomor klip yang berlubang dan list yang diacak. Pastikan judul, selection, dan expected duration tetap cocok. Koreksi ini diperlukan agar laporan cold run yang gagal sebagian tidak memberikan kesimpulan media yang salah.

## 3. Catatan bukti yang dapat dirapikan bersama koreksi runner

### Counter polling belum mengukur polling

[Counter `polling`](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/scratch/run_validation_v3.py:70) diinisialisasi dan direset, tetapi tidak pernah ditambah. Runner memasang wrapper `Files.upload` dan `Files.delete`, tanpa wrapper `Files.get`. Produksi menggunakan `client.files.get` ketika upload berstatus PROCESSING. Karena itu angka polling 0 saat ini dapat berarti “belum diinstrumentasi”, bukan “tidak ada polling”.

Tambahkan pencatatan `Files.get` saat merapikan wrapper File API untuk V3-01, atau beri label metrik itu belum diukur. Ini tidak mengubah cap inferensi dan tidak memerlukan audit ulang terpisah.

### Tepat tiga chunk bergantung pada isi transkrip

Simulasi 40/45 menit dengan ucapan tersebar sepanjang durasi memang menghasilkan tiga chunk dan empat panggilan LLM. Namun produksi tidak memasukkan chunk tanpa segmen. Probe tambahan menggunakan duration 2400 detik dengan ucapan hanya sampai sekitar 1199 detik menghasilkan dua chunk.

Ubah klaim dokumen menjadi “tiga chunk diharapkan apabila transkrip mencakup ketiga rentang; jumlah aktual dibuktikan lewat log”. Rentang 40–45 menit membatasi jumlah chunk maksimal tiga pada konfigurasi sekarang; simulasi belum menjamin isi transkrip nyata.

### Jenis bukti kandidat dan profiling

Wrapper audit menyimpan hasil `call_highlight_api` sesudah parsing/sanitasi, tetapi sebelum offset dan deduplikasi. Itu berguna sebagai kandidat relatif yang tervalidasi. Sebut tahap tersebut secara akurat; berkas ini bukan respons LLM mentah dan tidak menyimpan respons ranking invalid yang gagal sebelum fungsi kembali.

Runner memiliki log bertimestamp, tetapi belum ada pengukuran peak RAM pada kode yang diperiksa. Metrik yang belum diinstrumentasi harus tetap ditandai “Belum terukur”. Preflight saat ini juga membuktikan keberadaan folder/berkas cache, bukan SHA-256; bukti hash berasal dari suite/probe terpisah.

## 4. Hal yang sudah memenuhi persyaratan

- HEAD sesuai baseline dan `shorts_generator/` serta `web_app.py` tanpa perubahan.
- Binding output/cache Video 3 terisolasi sebelum impor pada proses runner bersih.
- OpenAI `max_retries=0` dipaksakan dan `MAX_HIGHLIGHT_API_ATTEMPTS=1` diterapkan dalam harness.
- Request highlight kelima serta transkripsi kedua diblokir pada tes offline, dan jalur fallback produksi yang diuji ditolak sebelum dispatch.
- SDK Gemini terpasang dengan retry options default `None` memakai satu attempt dalam pemeriksaan lokal. Tidak ditemukan bukti retry Gemini tersembunyi pada konfigurasi ini; jangan menambahkan temuan kuota berdasarkan asumsi retry SDK.
- Ranking JSON invalid dan daftar highlight kosong berhenti setelah satu percobaan.
- Simulasi 40 menit membuktikan tiga offset 0/1140/2280, empat call LLM, dan penambahan offset yang benar; simulasi 45 menit membuktikan tidak terbentuk chunk keempat.
- Kandidat per chunk ditulis sebelum offset/deduplikasi, dan rancangan summary per job serta pointer terbaru tersedia.
- Sepuluh artefak referensi Video 1/2 tetap identik SHA-256 dibanding bukti review terdahulu.

## 5. Bukti eksekusi dan batas verifikasi

| Bukti | Hasil / batas |
| --- | --- |
| Suite `test_guards_v3_offline.py` dijalankan ulang auditor | **8 tes, 5,024 detik, OK**, exit 0 |
| Probe independen runner | Empat skenario stop saat SDK menunggu menunjukkan gap V3-01; fixture hasil parsial menunjukkan V3-02 |
| Artefak preflight yang diserahkan | Dibaca, status PASSED; binding diperiksa ulang melalui suite offline. Preflight tidak dijalankan ulang untuk mempertahankan berkas bukti yang diserahkan |
| Suite penuh 108 tes | Hasil 36,635 detik berasal dari laporan pelaksana; auditor tidak mengulang suite penuh karena kode produksi tidak berubah dan verifikasi independen sebelumnya sudah lulus |
| Pemeriksaan media baru Video 3 | Belum dilakukan; sumber definitif belum ada |
| API nyata / download oleh auditor | 0 |

SHA-256 berkas yang direview:

- Runner: `15AAC68A90F579572707BD479B27F07AF0EE67AA3C4C75F513C02BA09E62086C`.
- Suite guard: `EE9DE0B391720E68796028124697245A53E4E69577F1A2F50207F24EA03C25A1`.
- Preflight yang diserahkan: `A6BCC809BCE0838C76DF02824C258FFE75C12AFAFB99BA27948BB16225A80D90`.

Bukti auditor:

- [Log delapan tes guard](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_guard_suite.txt).
- [Hasil probe independen](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_preparation_probes.json).
- [Harness probe offline](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v3_preparation_probes.py).

## 6. Arahan penutupan

Batasi tindak lanjut pada runner dan tes offline terkait V3-01/V3-02. Rapikan counter polling serta label bukti dalam pengerjaan yang sama. Tidak perlu mengulang audit A–C atau browser QA untuk perubahan harness ini.

Pemilihan sumber, bahasa, provider/model, dan kuota dapat dilakukan sambil dua koreksi tersebut dikerjakan. Setelah guard tambahan lulus dan parameter disepakati, lanjutkan satu cold run terkontrol. Pertahankan nominal maksimal satu transkripsi dan empat highlight; tidak ada pengulangan berbayar otomatis. Empat request adalah batas jumlah dispatch, bukan bukti biaya aktual atau jaminan hasil tiga klip siap publikasi.
