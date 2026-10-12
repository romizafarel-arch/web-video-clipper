# Review independen patch ketahanan transkripsi Video 3

Tanggal: 29 September 2026 (UTC+07:00).  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.  
Baseline: `main` / `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`.

## Keputusan

**Patch menunjukkan kemajuan nyata pada fixture Video 3, tetapi belum disahkan sebagai recovery konservatif yang siap digunakan untuk replay berbayar.** Empat koreksi di bawah dibatasi pada tiga berkas produksi yang sudah berubah. Dua temuan pertama menghalangi sign-off karena kasus ambigu masih dapat diperlakukan sebagai timestamp terpercaya.

Runner Video 3, Bagian A–C, dan penutupan teknis Video 2 tetap ditutup. Tidak perlu framework baru, fallback provider, perombakan pipeline, atau putaran audit seluruh proyek. Reviewer tidak mengubah kode produksi dan tidak menjalankan API berbayar.

## Bukti yang diperiksa dan hasil independen

- Diff tiga berkas produksi: `local/gemini_transcriber.py`, `local/transcriber.py`, `highlights.py`; suite baru `tests/test_v3_transcript_robustness.py`.
- **118/118 unittest lulus**, 30,865 detik, exit 0. Ini mencakup sepuluh tes baru. Koneksi jaringan diblokir dan output suite diisolasi pada folder reviewer.
- **21/21 guard offline lulus**, 8,128 detik, exit 0, dengan koneksi jaringan diblokir.
- Replay fungsi sumber aktual mengonfirmasi 5.851 kata, **3 estimated words**, **129 untrusted words**, **5 spans**, **34,10 detik** total gap dan **713 segmen**. Input raw tidak berubah dan kontrak cache pada fixture tersebut lulus.
- Integrasi `get_highlights` pada tiga chunk, dengan respons LLM buatan: klasifikasi satu kali, ranking tiga kali; kandidat chunk kedua yang melintasi gap dibuang, kandidat aman dikembalikan dengan offset absolut yang benar. Ini bukan eksekusi LLM berbayar atau bukti kualitas editorial.
- **65 berkas V1/V2 identik sebelum/sesudah pengujian reviewer**. Sepuluh checksum historis dari review sebelumnya juga dibandingkan dan tetap identik. Klaim seluruh 65 identik terhadap kondisi sebelum patch tidak dapat dibuktikan retrospektif tanpa manifest historis lengkap; bukti reviewer mencakup preservasi selama review dan sepuluh referensi historis.
- `.env`, sumber Video 3 dan diagnostik raw tidak berubah selama suite reviewer. Tidak ada publikasi hasil probe ke cache proyek.

## Temuan yang perlu ditindaklanjuti

### V3-T01 — P1: Eligibility recovery belum memenuhi batas konservatif

Lokasi: `shorts_generator/local/gemini_transcriber.py:430`, `:500`, `:534`.

Deteksi menggunakan `if inverted ... elif out_of_bounds`. Saat satu kata memenuhi kedua kondisi, status OOB tidak tercatat. Eligibility berikutnya membaca string alasan sehingga larangan recovery OOB tidak aktif. Pemeriksaan massive reset hanya mencakup lonjakan ke belakang, bukan raw endpoint yang melompat jauh ke depan.

Probe langsung terhadap fungsi aktual:

| Kasus | Hasil saat ini |
| --- | --- |
| Sumber 10s; anchor 0–1s dan 2–3s; kata raw 9999–1,5s | Diinterpolasi menjadi 1–2s, tanpa untrusted span; kontrak cache menerima |
| Sumber 100s; anchor sama; kata raw 90–1,5s | Diinterpolasi menjadi 1–2s, tanpa untrusted span |
| Tidak ada anchor kiri; raw 90–1,5s lalu kata 2–3s | Waktu 0 dianggap anchor, menghasilkan interpolasi 0–2s |
| Tidak ada anchor kanan; kata terakhir terbalik 9,7–9,3s pada sumber 10s | EOF dianggap anchor, menghasilkan interpolasi 9–10s |

Window hasil yang pendek tidak membuktikan bahwa kerusakan raw bersifat lokal. Batas file 0/EOF juga bukan bukti posisi ucapan. Semua hasil probe ini lolos schema, sehingga validator akhir tidak menyelamatkan keputusan recovery.

**Koreksi minimum:** catat semua kondisi cacat secara independen; OOB tidak boleh hilang ketika inverted atau saat pengelompokan. Untuk interpolasi, wajib ada dua anchor kata terpercaya dan batas deviasi raw terhadap window yang eksplisit, berlaku ke depan dan belakang. Angka besar, OOB, atau anchor hilang menjadi untrusted/quality rejection. Jangan mengganti algoritme dengan swap atau clamp umum. Tambahkan empat regresi probe di atas dan pastikan data overlap sah tetap dipertahankan.

### V3-T02 — P1: Spike end yang tidak inverted tetap dipakai sebagai anchor/segmen

Lokasi: `shorts_generator/local/gemini_transcriber.py:430` dan segmentasi sesudahnya.

Probe sumber 100s: `left=10–11`, `spike=11,1–99`, `right=12–13`. Semua endpoint berada dalam sumber dan semua pasangan berurutan. Sanitizer menghasilkan **nol audit/gap**, lalu segmenter menghasilkan `left spike` pada **10–99s**, disusul `right` pada 12–13s. Kontrak cache menerima keduanya.

Ini kasus spike end yang diminta dalam mandat, tetapi belum tercakup tes baru. Raw start watermark tidak mendeteksi end yang melompat. Endpoint dalam durasi media saja tidak cukup untuk menjadikannya anchor terpercaya.

**Koreksi minimum:** tambahkan deteksi endpoint/durasi kata yang mencurigakan dalam konteks tetangga sebelum pemilihan anchor. Blok ambigu harus dikarantina atau ditolak dengan alasan jelas. Jangan memotong semua end ke start kata berikutnya karena overlap pembicara yang sah harus tetap didukung. Tes harus membuktikan kasus di atas tidak lolos sebagai segmen terpercaya atau mengotori anchor berikutnya.

### V3-T03 — P2: Kontrak cache belum memeriksa batas durasi media

Lokasi: `shorts_generator/local/transcriber.py:93`, `_write_transcript_cache`, `_load_transcript_cache`.

Kontrak menerima `duration=10`, segmen `9–90`, dengan `untrusted_spans=[]`. Probe fungsi writer/loader aktual menggunakan media identitas buatan, output temporary terisolasi, dan probe fisik yang dimock 10s: JSON dan SRT dipublikasikan; loader memuat kembali segmen 9–90s sebagai valid.

Ketiadaan upper-bound sudah ada sebelum patch; klaim perlindungan publikasi cache dalam lingkup recovery saat ini belum menutupnya. Ini tidak membuka ulang Bagian C. Tempatkan koreksi pada kontrak yang memang sedang diperkuat.

**Koreksi minimum:** periksa start/end segmen dan span terhadap durasi sumber yang dipercaya, pada validasi final sebelum publikasi serta saat load. Jika writer mengganti duration berdasarkan probe sumber, validasi juga metadata final tersebut. Gunakan toleransi yang dinyatakan secara eksplisit dan konsisten. Tes segmen/gap di luar sumber harus membuktikan tidak ada cache baru dipublikasikan dan cache invalid tidak direuse.

### V3-T04 — P2: Anchor overlap menghasilkan untrusted span terbalik

Lokasi: `shorts_generator/local/gemini_transcriber.py:500`, `:561`, `:583`.

Probe: anchor kiri 10–20s, token rusak 15–15,1s, anchor kanan 16–21s. Window negatif sudah menolak interpolasi, tetapi helper masih mengeluarkan span **20–16s**. Jumlah gap menjadi −4s dan segmenter tidak menolaknya; validator cache akhirnya menolak metadata ini.

Jalur akhirnya gagal dengan jujur, sehingga temuan ini tidak menunjukkan cache rusak berhasil dipublikasikan. Namun metadata quarantine dan quality fraction salah, dan sumber kegagalan baru muncul terlambat pada cache. Ini merusak kontrak antara sanitizer dan konsumennya.

**Koreksi minimum:** helper harus menghasilkan interval quarantine finite, terurut dan berada dalam media, atau langsung melempar error kualitas yang menjelaskan anchor overlap. Jangan sekadar menukar batas gap tanpa menentukan rentang yang benar-benar perlu dikecualikan. Quality fraction tidak boleh menerima durasi negatif; jika span valid saling overlap, hitung cakupan gabungannya. Tambahkan regresi overlap di atas serta kasus awal/akhir tanpa anchor.

## Penilaian arsitektur dan kualitas bukti

Pemisahan sanitizer → segmenter → kontrak cache → filter highlight sudah berada pada komponen yang tepat, menggunakan struktur standar dan tanpa dependensi baru. Filter global dilakukan setelah offset chunk dan sebelum deduplikasi, sehingga kandidat valid berskor lebih rendah tidak hilang akibat kandidat yang melintasi gap. Metadata recovery/spans tetap tersimpan setelah cache roundtrip.

Kelemahannya adalah eligibility bergantung pada satu string alasan yang dapat menutupi kondisi lain. Perbaiki representasi/prasyarat lokal tersebut; tidak perlu menulis ulang seluruh delapan pass atau menambah abstraksi generik.

Threshold window 5s, enam kata, lima kata/detik, reset 5s dan gap 25% adalah parameter kebijakan, bukan hasil pembuktian ketepatan subtitle. Sepuluh tes lulus pada contoh yang diberikan, tetapi belum menguji seluruh batas kebijakan. Tetap uji kondisi aman/tidak aman; assertion jumlah 713/3/5 tidak boleh menjadi alasan mempertahankan keputusan recovery ketika aturan diperbaiki.

Pada output fixture, flag `estimated` ada pada word internal; segmen akhir tidak membawa flag itu. `recovery_audit` masih menyimpan rentang koreksi sehingga provenance tidak hilang seluruhnya, tetapi replay harus menggunakannya untuk menandai klip yang melewati area estimated. Klaim laporan bahwa patch sudah memiliki “ketahanan penuh” dan “tanpa mengorbankan ketepatan waktu” belum didukung pembandingan dengan audio. Reviewer belum mendengarkan bagian 512,6–515,2s.

## Keputusan mengenai replay/resume terkontrol

**Pendekatannya tepat dan dapat menghemat satu request STT, tetapi sign-off eksekusi ditunda sampai koreksi terbatas di atas selesai.** Tidak perlu transkripsi baru untuk memperbaiki atau menguji empat kasus ini.

Setelah itu, replay menggunakan sumber dan raw response yang sama, dengan:

1. Manifest asal: Job ID gagal asli, path/SHA source dan fixture, baseline serta hash patch, versi sanitizer, daftar gap dan recovery audit.
2. Guard replay menolak seluruh STT/File upload baru; counter STT harus nol. Maksimal empat highlight tetap memerlukan izin penggunaan API yang berlaku untuk run baru.
3. Output sesi baru yang tidak menimpa cold run gagal atau fixture; status ditulis sebagai controlled replay/resume.
4. Kandidat otomatis tidak beririsan dengan untrusted spans. Rentang estimated ditandai untuk pemeriksaan manual atau dikecualikan pada pilot pertama.
5. Verifikasi media fisik hasil serta inspeksi audiovisual/editorial dilakukan setelah render. Target tiga klip tetap target; kurangnya kandidat aman harus dilaporkan jujur.

Ini memvalidasi pemakaian respons STT tersimpan untuk highlight/render, bukan bukti STT baru berhasil atau sanitizer dapat menangani seluruh output provider.

## Artefak reviewer

Folder: `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`.

- `review_v3_patch_probes.py` / `.json`: fungsi produksi diambil langsung melalui AST; enam counterexample, replay fixture, writer/loader cache dan integrasi chunk/highlight. Jaringan diblokir, LLM serta probe durasi cache menggunakan fixture/mock.
- `review_v3_patch_full_suite.log` / `_result.json`: 118/118, exit 0.
- `review_v3_patch_guards_suite.log` / `_result.json`: 21/21, exit 0.
- `review_v3_patch_preservation_before.json`: checksum 65 berkas V1/V2 serta .env, source/diagnostik V3 sebelum suite.
- `review_v3_patch_historical_preservation.json`: sepuluh referensi historis tetap identik.
- `review_v3_patch_source_hashes.json`: fingerprint kode yang direview.

SHA-256 adapter Gemini saat review: `14e808dd4a86c1399ea0cf6db73af6166da6cadbeab08e072c3b8a54510decdd`.
