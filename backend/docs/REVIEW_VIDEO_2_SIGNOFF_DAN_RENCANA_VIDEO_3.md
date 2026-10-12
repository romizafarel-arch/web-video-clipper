# Review Penutup Video 2 dan Kesiapan Rencana Video 3 — ShortsStudio

Tanggal review: 29 September 2026, zona waktu UTC+07:00.

Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.

Commit yang diperiksa: `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`, branch `main`. Baseline pembanding: `fb3aee9b156dabb8ec1b0b14913f189208507766`.

## 1. Keputusan

**V2-C01 disahkan selesai. Validasi teknis Video 2 dapat ditutup dan baseline bbd2c4d layak untuk pemilihan sampel serta persiapan Video 3.** Tidak ditemukan blocker baru pada koreksi cancellation yang diperiksa. Bagian A–C tetap ditutup.

Penutupan teknis ini tidak menyatakan ketiga klip Video 2 siap publikasi. Masalah framing, batas potongan, serta verifikasi audiovisual manual tetap mengikuti status editorial dalam laporan Video 2. Persiapan Video 3 dapat berjalan bersamaan dengan penyempurnaan editorial pada media Video 2 yang sudah ada.

Eksekusi berbayar Video 3 belum dilakukan dalam review ini. Sumber, konfigurasi, bahasa, dan kuota perlu ditetapkan sebelum pelaksanaan. Guard Video 3 masih berupa rancangan; kesiapan runner baru harus dibuktikan melalui preflight tanpa API sebelum pengguna mengizinkan run.

## 2. Bukti independen yang diperoleh

| Pemeriksaan | Hasil review |
| --- | --- |
| Identitas HEAD | Sesuai `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e` |
| Suite unittest seluruh repositori | **108 tes, 34,841 detik, OK**, exit code 0 |
| Suite transkrip Video 2 | Seluruh 23 tes tercakup dan lulus dalam discovery tersebut |
| Hashing normal | SHA-256 streaming cocok dengan hash fixture sumber |
| Cancel selama hashing | `JobCancelledException` keluar; diagnostik tidak dipublikasikan |
| Timeout selama hashing | `JobTimeoutException` keluar; diagnostik tidak dipublikasikan |
| Jalur transkripsi dengan SDK mock | Kedua exception diteruskan; satu generate, satu upload, satu upaya delete; tidak mengembalikan transkrip dan tidak memanggil fallback |
| Kontrak timestamp | Interval 10,00–10,02 tetap 0,02 detik; interval nol dipertahankan; boolean ditolak |
| Preservasi setelah suite selesai | **10/10 artefak identik SHA-256**, termasuk tiga cache Video 1, sumber/audio Video 2, bukti job lama, dan tiga MP4 final Video 2 |
| Perubahan kode oleh auditor | Tidak ada |
| Permintaan API nyata oleh auditor | Tidak ada |

Suite memakai fixture lokal dan FFmpeg nyata pada tes media; perilaku SDK/model dikendalikan mock. Pesan decoder `moov atom not found` muncul dalam rangkaian tes berkas korup; hasil suite tetap OK. Probe tambahan mengeksekusi fungsi dari AST kode produksi terkini, dengan SDK diganti fixture offline.

Review ini tidak mengulang pemutaran audiovisual menyeluruh terhadap tiga klip. Bukti decode dari review sebelumnya tetap relevan karena hash MP4 tidak berubah, tetapi tidak diperlakukan sebagai bukti bahwa hook, lip sync, atau sinkronisasi subtitle terhadap ucapan telah dinilai manual.

## 3. Penilaian arsitektur V2-C01 dan kecukupan regresi

Urutan penanganan exception sudah tepat untuk lingkup temuan: checkpoint hashing melempar exception kontrol, handler khusus meneruskannya sebelum handler umum, Path A transkripsi meneruskan lagi sehingga tidak masuk fallback, dan caller tidak mencapai penulisan cache ketika transkripsi gagal karena cancel/timeout.

Referensi implementasi:

- [Hashing dan handler diagnostik](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:448): handler khusus pada baris 457 dan 499.
- [Handler Path A](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:632): exception kontrol diteruskan sebelum fallback generik.
- [Caller dan publikasi cache](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/transcriber.py:362): publikasi mengikuti pengembalian transkrip, sehingga exception menghentikan jalur itu.

Hashing berblok 64 KB menghilangkan pembacaan seluruh video ke RAM untuk kebutuhan SHA-256. Ini tidak membuktikan penggunaan RAM seluruh pipeline konstan: daftar kata, transkrip, dan struktur diagnostik tetap bertambah sesuai banyaknya data. Peak RAM Video 3 masih perlu diukur.

Suite 23 tes memadai untuk menutup regresi yang dibahas, dengan bukti berlapis pada helper, wrapper SDK, caller/cache, dan lifecycle worker. Tes worker menginjeksi exception pada `generate_shorts`; tes tersebut menguji pemetaan status memori/disk, bukan satu eksekusi berkelanjutan dari hashing sampai worker melalui API nyata. Upaya delete yang teramati pada mock juga tidak membuktikan penghapusan berhasil di layanan Gemini.

**Catatan kualitas tes, tidak menghalangi sign-off:** beberapa tes mengganti `cfg.LOCAL_OUTPUT_DIR`, sementara helper diagnostik menggunakan konstanta `LOCAL_OUTPUT_DIR` yang diimpor ke namespace modul. Assertion file tidak ada pada folder sementara menjadi kurang kuat karena folder tersebut belum tentu folder tujuan helper. Saat merapikan tes, patch `shorts_generator.local.gemini_transcriber.LOCAL_OUTPUT_DIR` langsung. Probe independen review ini menggunakan namespace tujuan yang benar dan menutup kekurangan bukti untuk keputusan sekarang. Penambahan kasus timeout pada tes caller/cache dapat dilakukan ketika tes itu disentuh; tidak perlu membuka ulang V2-C01.

## 4. Proporsionalitas chunk dan kuota Video 3

Probe terhadap `chunk_transcript` terkini, menggunakan fixture transkrip yang mencakup seluruh durasi, menghasilkan:

| Durasi sumber | Chunk | Offset chunk, detik | Kebutuhan highlight nominal tanpa retry |
| --- | --- | --- | --- |
| 35 menit | 2 | 0, 1140 | 3 |
| **40 menit** | **3** | **0, 1140, 2280** | **4** |
| **45 menit** | **3** | **0, 1140, 2280** | **4** |
| 58 menit | 3 | 0, 1140, 2280 | 4 |
| 60 menit | 4 | 0, 1140, 2280, 3420 | 5 |

Pemilihan 40–45 menit proporsional untuk membuktikan tiga chunk tanpa menambah chunk keempat. Jumlah aktual tetap harus diperiksa dari transkrip/log karena chunk tanpa segmen tidak dimasukkan. Pilih sumber yang masih memiliki ucapan setelah detik 2280 agar chunk ketiga benar-benar diuji.

Empat request highlight berarti satu klasifikasi dan tiga ranking per chunk. Penggabungan, deduplikasi, dan pengurutan skor dilakukan lokal; tidak diperlukan request LLM tambahan untuk ranking global. Tiga klip adalah target keluaran, bukan jaminan jumlah kandidat valid atau jumlah render sukses.

Rentang efektif chunk umumnya 0–1260, 1140–2400, dan 2280–akhir. Tambahkan pemeriksaan overlap kedua 2280–2400. Untuk video tepat 40 menit, area `>2400s` kosong; definisikan pemeriksaan akhir berdasarkan durasi aktual, misalnya dua menit terakhir. Kontribusi chunk harus dibuktikan dengan log dan kandidat sebelum offset/deduplikasi, bukan timestamp final saja.

## 5. Mitigasi latensi paling kecil yang diperlukan

Latensi satu ranking Video 2 sebesar sekitar 268 detik merupakan satu observasi. Perkalian menjadi sekitar 804 detik untuk tiga ranking hanya skenario kapasitas, bukan prediksi terukur untuk prompt Video 3 yang lebih panjang. Klasifikasi, upload, transkripsi, ekstraksi, render, dan verifikasi masih harus ditambahkan. Angka transkripsi 60–120 detik, render 250–350 detik, dan total 1100–1300 detik dalam draft perlu diberi label asumsi atau diganti “belum terukur”. Rendering tiga klip juga tidak sama dengan merender ulang seluruh video sumber 40 menit.

**Batas 1800 detik sekarang bersifat kooperatif.** [JobContext](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/job_manager.py:195) memeriksa waktu pada checkpoint. [Pemanggilan OpenAI lokal](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/llm.py:35) bersifat sinkron dan tidak memasang timeout request yang diturunkan dari sisa deadline job. Karena itu, tidak ada jaminan worker berhenti persis pada detik 1800 ketika SDK masih menunggu jaringan.

Rekomendasi untuk runner Video 3, tanpa perombakan arsitektur:

1. Pertahankan pemrosesan tiga chunk secara berurutan untuk run validasi pertama dan ukur tiap request. Parallel ranking belum diperlukan untuk memperoleh bukti dasar yang dapat ditelusuri.
2. Bungkus request dalam harness dengan checkpoint sebelum/sesudah pemanggilan, perhitungan sisa deadline, dan timeout jaringan yang sesuai sisa waktu serta cadangan render/cleanup. Jangan mulai request berikutnya ketika anggaran waktu tidak memadai. Cadangan waktu harus dinyatakan sebagai parameter perencanaan, bukan hasil pengukuran baru.
3. Tetapkan `max_retries=0` dan **satu percobaan ranking pada tingkat aplikasi** dalam proses harness. [Kode produksi](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/highlights.py:70) masih memiliki `MAX_HIGHLIGHT_API_ATTEMPTS = 3`; menghapus retry SDK saja tidak menghapus retry karena JSON tidak valid. Uji mock harus membuktikan respons invalid tidak mengirim request pengganti, selain memeriksa cap total empat highlight.
4. Saat deadline job habis, teruskan `JobTimeoutException` melalui guard; jangan mengubahnya menjadi error generik atau fallback. Counter, latensi, status, dan upaya cleanup tetap dicatat jika run berhenti.

Timeout jaringan dan checkpoint memperkecil risiko menggantung; keduanya belum membuktikan batas wall-clock keras untuk semua perilaku SDK. Jika dibutuhkan penghentian keras tepat 1800 detik, supervisor proses terpisah menjadi pekerjaan tersendiri. Kebutuhan tersebut tidak perlu ditambahkan hanya untuk menyetujui pemilihan sampel sekarang. Jangan menjanjikan run pasti selesai di bawah 1800 detik sebelum Video 3 diukur.

## 6. Langkah berikutnya

1. **Boleh langsung memilih sampel lokal 40–45 menit**, dengan ucapan berlanjut sampai bagian akhir. Rekam durasi fisik, resolusi, ukuran, mtime, bahasa, dan hash.
2. Rapikan draft secara terbatas: overlap kedua dan zona akhir aktual, label asumsi waktu, serta target tiga klip yang dapat menghasilkan lebih sedikit jika kandidat tidak cukup. Gunakan empat kategori publikasi awal—Siap Dipakai, Perlu Edit Ringan, Perlu Edit Besar, Tidak Layak—dan tempatkan “belum dinilai audio” sebagai status pemeriksaan terpisah.
3. Siapkan runner/preflight Video 3 terisolasi ke `output_val_v3` dengan guard empat highlight, satu transkripsi, tanpa fallback/retry, serta kontrol deadline. Buktikan guard dengan mock offline; tidak perlu menjalankan ulang seluruh audit A–C.
4. Setelah sumber, konfigurasi, bahasa, dan kuota disepakati, lakukan satu cold run. Laporkan hasil sesungguhnya, termasuk status timeout/partial bila terjadi, tanpa pengulangan berbayar otomatis.

Tracked working tree tetap tanpa perubahan saat pemeriksaan selesai; artefak validasi terdahulu masih untracked. Commit baru tidak memasukkan `.env`, media output, cache, atau virtual environment dalam daftar perubahan. Dokumen review ini merupakan artefak baru terpisah, bukan perubahan kode produksi.

## 7. Inventaris bukti review

- [Log suite 108 tes](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v2_signoff_unittest.txt).
- [Hasil probe kontrol dan chunk](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v2_signoff_probes.json).
- [Skrip probe offline](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v2_signoff_probes.py).
- [Preservasi SHA-256 setelah tes](C:/Users/ASUS/.codex/visualizations/2026/09/28/01a0e5fd-90b3-7972-9035-3069a8f936e6/review_v2_signoff_preservation_after_tests.json).
- [Draft rencana Video 3](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/docs/RENCANA_VALIDASI_VIDEO_3_PANJANG.md).

