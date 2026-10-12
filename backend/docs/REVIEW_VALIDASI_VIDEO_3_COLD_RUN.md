# Review independen cold run Video 3 — ShortsStudio

Tanggal: 29 September 2026 (UTC+07:00).  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.  
HEAD terverifikasi: `main` / `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`.  
Run yang diperiksa: `val_v3_long_72842` / `20260929_160722_val_v3_long_72842`.

## Keputusan

**Disiplin eksekusi dan guard yang terpakai pada cold run ini sesuai protokol. Pipeline Video 3 gagal pada transkripsi; validasi end-to-end video panjang belum lulus.**

Koreksi runner tetap ditutup. Bagian A–C dan penutupan teknis Video 2 tetap berlaku. Temuan baru merupakan masalah ketahanan adapter terhadap data STT nyata, bukan alasan mengulang audit runner. Tidak ada kode produksi atau API berbayar yang dijalankan/diubah oleh reviewer.

Rekomendasi patch dalam laporan pelaksana yang menukar waktu atau meratakan semua kata belum layak diterapkan apa adanya. Validasi ketat berhasil mencegah timestamp rusak dipakai oleh renderer; recovery harus mempertahankan perlindungan tersebut.

## Bukti eksekusi yang diverifikasi

| Area | Hasil independen |
| --- | --- |
| Sumber | 112.410.774 byte; SHA-256 `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` |
| Metadata fisik | FFprobe: durasi 2.630,658322 detik, H.264 Main 1280×720, 30000/1001 fps, AAC LC stereo 44.100 Hz |
| Decode sampel | FFmpeg `-xerror`, masing-masing 5 detik pada 10, 1200, 2350: exit 0, stderr kosong; frame OpenCV terbaca, shape 720×1280×3 |
| Aktivitas audio akhir | Volumedetect 2280–2480 detik: mean −24,5 dB, max −3,8 dB |
| Run | Ringkasan dan metadata disk konsisten: failed, 119,85 detik wall-clock, 119,81 detik metadata, tidak ada short MP4 |
| Worker/admission | Snapshot akhir runner: worker tidak hidup; dua getter active job bernilai null |
| Inferensi | Counter mencatat satu STT dispatched, nol highlight, satu fallback diblokir sebelum dispatch |
| File API | Counter: upload 1, polling 0, delete 1, delete_success 1, delete_failed 0 |
| Cache | Audio MP3 tersedia; direktori cache transkrip V3 kosong; tidak ada transkrip gagal dipublikasikan sebagai cache valid |
| Pointer summary | JSON pointer sama dengan summary per-job |
| Preservasi | Sepuluh referensi SHA-256 V1/V2 dari review penutup terdahulu tetap identik sesudah cold run |
| Produksi/runner | Diff produksi kosong; SHA runner tetap `3b5e4eef614327a7216bfb72a8cd212541b4bf18b830f75b42c8b3e0a6a306b1` |

Preflight tersimpan sebelum run dan binding config/transcriber/web_app menunjuk output_val_v3. Counter dan log mendukung kepatuhan satu eksekusi yang diperiksa; tidak merupakan audit seluruh request jaringan akun/billing atau inventaris cloud.

## Akar masalah dan perluasan temuan

Diagnostik berukuran 751.150 byte berisi 5.851 kata. Fungsi `_parse_offset` dan `_words_to_segments` dari sumber produksi aktual direplay offline pada data tersebut. Kegagalan pertama identik dengan diagnostik: indeks berbasis nol 1228, `hyper`, start 516,3 / end 514,6 detik. Parser hanya mengubah nilai offset menjadi angka; tidak ditemukan konversi unit yang menjelaskan pembalikan ini. Nilai sudah bermasalah pada data yang diterima adapter sebelum segmentasi. Bukti tersimpan bukan raw HTTP response, sehingga tidak mengisolasi model versus lapisan SDK lebih jauh.

Analisis independen mengonfirmasi:

- **28 kata terbalik**, **36 start backward jump**, serta **4 kata memiliki setidaknya satu endpoint melewati durasi sumber**. Kategori tersebut saling beririsan.
- Pasangan `hyper arousal` muncul dua kali dengan teks dan offset yang identik pada 1228–1231. Ini bukti pengulangan payload, belum bukti bahwa pengulangan ucapan di audio adalah halusinasi.
- Kerusakan juga mengenai kata yang memenuhi `end >= start`: indeks 4612–4615 berada di sekitar 1010 detik setelah konteks 2009 detik; indeks 5502–5515 berada di sekitar 440 detik setelah konteks 2439 detik.
- Blok sekitar indeks 2519–2575 melibatkan endpoint 12010,1 dan reset ke sekitar 120–139 detik di tengah konteks 1119–1140 detik. Pada 5429–5476 muncul reset ke 0,2 detik dan token `/?` di tengah konteks 2419–2426 detik. Satu perbaikan kata tidak menyelesaikan blok ini.

**Counterexample offline:** semua pasangan terbalik ditukar lalu dilewatkan ke segmenter aktual. Hasilnya 743 segmen, termasuk 11 segmen yang berakhir di luar sumber atau memiliki span lebih dari 60 detik. Contoh: `mengembalikan` menjadi 0,2–2419,8 detik; `jadi` menjadi 120,3–12010,1 detik. Threshold 60 detik di sini hanya indikator anomali pada replay, bukan spesifikasi durasi kata baru. Hasil ini tidak disimpan ke cache produksi.

## Klasifikasi dan batas klaim

Layak diprioritaskan **P1 untuk jalur validasi Gemini video panjang ini**: pekerjaan berhenti setelah request berbayar menghasilkan respons, dan belum ada recovery konservatif. Ini kesenjangan ketahanan/data provider. Asert validasi yang menolak rentang rusak sendiri tidak salah; menghapusnya tanpa pengganti akan mengubah kegagalan jujur menjadi subtitle salah waktu.

Kualitas editorial, akurasi kata terhadap ucapan, ASS/VTT akhir, framing, kesiapan publikasi, pemrosesan tiga chunk, serta render panjang tetap **belum dinilai/belum teruji**, karena tahap highlight/render tidak berjalan. Satu run belum membuktikan bahwa model selalu/sering mengalami masalah pada semua video panjang.

Pelurusan laporan pelaksana:

1. `transcribe.success: 1` berarti wrapper menerima respons SDK, **bukan** transkrip lolos validasi. Tidak ada kontradiksi dengan status job failed.
2. Respons delete berhasil mendukung catatan cleanup berhasil menurut SDK; jangan memperluasnya menjadi inventaris seluruh cloud bebas artefak. Snapshot worker/admission juga belum merupakan pemeriksaan seluruh handle OS.
3. Volumedetect membuktikan adanya sinyal audio, bukan ucapan yang jelas atau bahasa tertentu. Reviewer tidak mendengarkan sumber; klaim tersebut belum diverifikasi secara independen.
4. Interval log 91,246 detik mencakup request transkripsi sampai penulisan diagnostik, bukan pengukuran murni latensi layanan. Ekstraksi 15,257 detik juga mencakup verifikasi audio/setup terkait. Waktu tahap yang tidak terpisah jangan dilabeli presisi palsu.

## Rancangan patch minimum yang direkomendasikan

Batasi pada adapter Gemini dan integrasi kontrak yang benar-benar diperlukan. Pertahankan `_parse_offset` serta validator akhir yang ketat; tambahkan helper recovery sebelum `_words_to_segments`, dengan durasi fisik sumber sebagai input. Tidak perlu framework sanitizer lintas-provider, provider fallback baru, atau chunking audio pada patch pertama.

1. **Simpan data mentah dan klasifikasi lebih dahulu.** Kerjakan salinan data. Catat perbaikan/penolakan, indeks asal, offset raw dan hasil, alasan, serta bagian yang memerlukan pemeriksaan. Missing/boolean/NaN/Infinity tidak otomatis diganti nol.
2. **Bedakan jitter kecil dari kerusakan blok.** Gunakan anchor tetangga yang finite, berada dalam durasi, dan konsisten secara lokal. Anchor yang sendiri out-of-bounds seperti 12010,1 tidak boleh menjadi baseline untuk meratakan seluruh sisa transkrip. Overlap dialog yang valid tetap didukung; jangan memaksa semua start monotonik dengan `max(prev_end, start)`.
3. **Recovery hanya pada rentang lokal yang dibatasi.** Koreksi kecil atau interpolasi dapat dicoba jika dua anchor terpercaya membatasi interval pendek dan jumlah kata masuk akal. Batas jitter/window adalah parameter konservatif yang diuji offline, bukan jaminan kebenaran audio. Tandai waktu hasil estimasi dan periksa terhadap sumber sebelum menyatakan sinkronisasi benar. Jangan menukar pasangan secara umum, menjepit seluruh reset ke EOF, menebak digit yang hilang, atau memberi semua kata durasi buatan 0,05 detik.
4. **Blok ambigu tetap terlihat.** Pertahankan teks aslinya dalam diagnostik; tandai span tak dapat dipercaya. Untuk melanjutkan dengan bagian valid, span tersebut harus dikecualikan dari pemilihan otomatis klip/subtitle dan tidak boleh dirangkai menjadi kalimat yang menyeberangi gap tanpa penanda. Jika pengecualian tidak dapat ditegakkan atau tidak cukup data terpercaya, hentikan dengan error kualitas yang jelas. Menahan hasil tetap benar dalam kasus ambigu; sanitizer tidak wajib memaksa fixture ini menjadi sukses.
5. **Duplikasi dengan bukti kuat saja.** Hapus hanya salinan payload exact dengan rentang valid yang sama dan identitas pembicara yang konsisten bila tersedia, disertai audit. Jangan menghapus repetisi alami atau kata yang sama pada waktu berbeda. Pasangan inverted `hyper arousal` belum memenuhi bukti waktu valid tersebut.
6. **Validasi sebelum publikasi cache.** Semua segmen harus finite dan berada dalam durasi sumber; tidak ada span besar palsu akibat repair, dan metadata gap/estimasi harus tetap tersedia bagi konsumen. Jika hasil repair disimpan untuk reuse, bedakan versi kebijakan sanitizer agar tidak dikira transkrip mentah tervalidasi atau mengabaikan quality flags. Jangan memasukkan diagnostik rusak ke cache secara manual.
7. **Pertahankan exception kontrol dan provenance error.** Cancel/timeout tetap dipropagasikan, cleanup tetap berjalan, dan ketika fallback diblokir log harus tetap mempertahankan penyebab validasi asli. Payload mentah serta keputusan recovery memungkinkan investigasi tanpa panggilan STT baru.

## Verifikasi patch dan langkah berikutnya

Gunakan diagnostik 5.851 kata sebagai fixture offline dengan sumber hash yang sama. Tes bermakna harus mencakup: data valid tidak berubah, jitter lokal, spike end yang tidak inverted, out-of-bounds, reset blok in-range, overlap dua pembicara yang valid, duplikasi exact versus repetisi alami, serta cancel/timeout. Assertion keberhasilan harus mencakup kontrak waktu dan quality flags; jumlah kata/segmen saja tidak cukup.

Replay fixture tidak perlu menghubungi Gemini, APMix, atau mengunduh media. Pertahankan baseline regresi dan checksum V1/V2. Pilih beberapa rentang yang dikoreksi untuk pembandingan audio sumber; jika belum didengar, sinkronisasi tetap belum dinilai.

Sesudah kebijakan recovery lulus offline dan bagian ambigu ditangani secara eksplisit, minta izin eksekusi berbayar yang masih diperlukan. Pilihan hemat adalah run lanjutan berbasis respons STT tersimpan melalui harness dengan provenance jelas, tanpa request STT baru, untuk menguji highlight/render pada bagian terpercaya. Labeli sebagai **replay/resume terkontrol**, bukan cold run kedua atau bukti reliabilitas STT baru. Jika membutuhkan transkripsi baru/realignment, tetapkan provider dan kuota secara eksplisit terlebih dahulu.

## Artefak reviewer

Semua artefak berada di `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`:

- `review_v3_cold_run_analysis.py` dan `.json`: audit raw words, replay parser aktual, counterexample swap, checksum preservasi.
- `review_v3_source_checks.py` dan `.json`: FFprobe, tiga sampel FFmpeg/OpenCV, volumedetect akhir.

Reviewer tidak menjalankan API berbayar, tidak mengubah kode produksi, tidak memublikasikan transkrip repair, dan tidak mengklaim inspeksi audiovisual hasil yang belum ada.
