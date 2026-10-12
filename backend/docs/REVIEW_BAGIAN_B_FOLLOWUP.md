# Review tindak lanjut Bagian B — ShortsStudio

Tanggal: 28 September 2026.
Checkout: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`, branch `main`, working tree lokal belum di-commit.

## Keputusan

**Belum disahkan selesai.** B-01, B-06, dan perbaikan suite B-07 sudah menunjukkan hasil yang baik. Empat koreksi konkret masih diperlukan pada B-02, B-03, B-04, dan B-05. Ini penutupan temuan lama, bukan penambahan fitur atau audit Bagian C.

Bagian A tetap ditutup: seluruh 41 regresinya lulus pada checkout terbaru.

## Bukti pengujian independen

- Suite penuh: **57/57 lulus**, 5,004 detik, **0 failure, 0 error, 0 skip**, tanpa menggantung. Termasuk render FFmpeg nyata dan timeout FFmpeg saat berjalan.
- Runner lifecycle terbaru dijalankan di **Google Chrome headless nyata** dengan aplikasi terbaru dan salinan persis berkas JS runner. Profil Chrome dan output berada di direktori sementara, bukan folder hasil pengguna.
- Ketujuh skenario runner browser lulus: UI cancellation, resume aktif, resume partial, interrupted, retry 503, pemulihan cancel HTTP 500, serta ukuran tombol dan fokus pada desktop/mobile.
- Tombol cancel: desktop 98,78 × 36 px; mobile 390 dan 320: 94,64 × 44 px. Kedua viewport mobile tanpa horizontal scroll. Fokus programatis diterima dan outline terukur 2 px solid.
- Batas bukti browser: job/state disuntikkan melalui test hooks; completion/cancellation akhir disimulasikan. Kartu partial memakai URL fixture yang mengembalikan 404, sehingga tes itu membuktikan render kartu, bukan pemutaran video. Pengujian fokus menggunakan `.focus()`, bukan rangkaian Tab fisik. Jangan menamai bukti ini sebagai pengujian seluruh pipeline generasi nyata.
- Probe tambahan memakai kode endpoint/gate/worker sebenarnya dengan source, render, dan fault fixture sementara. Tidak ada generasi AI berbayar selama review.
- Kode proyek dan hasil asli tidak diubah. Server/Chrome QA sudah keluar; port 5066 dan 9223 diperiksa kembali dan tertutup.

## B-05 — P1, masih terbuka: jalur Gemini gagal sebelum ekstraksi audio

Lokasi:
- [gemini_transcriber.py:11](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:11)
- [gemini_transcriber.py:33](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:33)
- [gemini_transcriber.py:57](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:57)
- [gemini_transcriber.py:66](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:66)
- [gemini_transcriber.py:89](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/gemini_transcriber.py:89)

Import langsung pada Python proyek menghasilkan:

```text
NameError: name 'Any' is not defined
```

`Any` dipakai pada annotation parameter `transcribe_with_gemini`, tetapi belum diimpor. Transkripsi Gemini yang belum memiliki cache gagal saat modul dimuat.

Selain itu, `_extract_audio_compressed` masih hanya menerima `media_path`, sedangkan caller mengirim `job_ctx=job_ctx`. Sesudah masalah import diperbaiki, pemanggilan itu akan menghasilkan TypeError. Body helper juga menggunakan nama `job_ctx` yang belum didefinisikan sebagai parameter.

Perbaikan minimum: perbaiki import dan signature helper serta teruskan konteks sampai shared FFmpeg runner. Pertahankan perubahan checkpoint API dan polling Gemini yang sudah dibuat.

Tes penutup: import modul nyata; jalankan `transcribe_local(provider='gemini', force_refresh=True)` dengan client Gemini tiruan dan fixture lokal, tanpa melewati helper yang sedang diuji. Buktikan job context mencapai ekstraksi audio. Tes existing API-mode cancellation tetap harus lulus. Tidak diperlukan panggilan Gemini berbayar.

## B-03 — P1, masih terbuka: set indeks klip kehilangan editor kedua

Lokasi:
- [web_app.py:156](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:156)
- [web_app.py:166](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:166)
- [web_app.py:173](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:173)
- [web_app.py:1582](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:1582)

SessionGate mendaftarkan operasi sebelum mengambil per-clip lock, tetapi menyimpan aktivitas dalam `Set[int]`. Dua permintaan untuk klip #1 menjadi satu entri `{1}`. Saat permintaan pertama selesai, `discard(1)` menghapus aktivitas permintaan kedua yang masih mengantre atau sudah mulai render.

Reproduksi endpoint nyata dengan render fixture disinkronkan:

1. Edit pertama klip #1 mulai render.
2. Edit kedua klip #1 sudah terdaftar dan menunggu clip lock.
3. Edit pertama selesai; edit kedua mulai render.
4. Gate mencatat **tidak ada editor aktif**.
5. DELETE mengembalikan **200** dan folder hasil terhapus; edit kedua mendapat **500**.

Ini masih risiko kehilangan hasil pada kriteria perlindungan delete. Gate untuk editor berbeda dan delete yang lebih dahulu berjalan sudah merupakan kemajuan, tetapi belum cukup untuk permintaan duplikat klip yang sama.

Perbaikan minimum: catat setiap operasi memakai penghitung referensi atau token permintaan unik. Unregister hanya mengurangi/menghapus operasi milik permintaan tersebut. Gunakan lock gate yang sama untuk pendaftaran, pelepasan, dan delete; pertahankan render klip berbeda secara paralel.

Tes penutup: dua request klip yang sama, request kedua yang timeout saat menunggu lock, serta dua klip berbeda. Delete harus tetap 409 selama masih ada satu operasi aktif. Sesudah semua keluar, delete boleh berhasil.

## B-02 — P1, masih terbuka: gagal menyimpan metadata awal membuat job aktif selamanya

Lokasi:
- [web_app.py:398](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:398)
- [web_app.py:409](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:409)
- [web_app.py:419](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:419)
- [web_app.py:1075](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:1075)

Admission menelan kegagalan persistensi dengan `except: pass`. Worker kemudian beralih ke running dan memanggil `_persist_job_metadata` **sebelum** masuk blok try/except/finally utama. Jika penulisan awal gagal, exception keluar dari thread tanpa finalisasi status.

Probe PermissionError penulisan metadata menghasilkan:

```text
POST generate: 200
worker alive: false
status: running
error: null
pipeline calls: 0
POST generate berikutnya: 409
```

Jadi proses sudah mati, tetapi admission tetap menganggapnya aktif. Pembatalan running juga tidak memiliki worker tersisa yang dapat menyelesaikan transisi canceling.

Perbaikan minimum: cakup pembuatan sesi, penulisan awal, dan start worker dalam penanganan error/finalisasi lifecycle. Jika persistensi yang diperlukan gagal, berikan kegagalan jelas dan lepaskan admission hanya setelah worker/sumber daya benar-benar selesai. State akhir dalam memori harus tetap tersedia meskipun disk tidak bisa ditulis. Jangan diam-diam melanjutkan job yang dijanjikan dapat dipulihkan tanpa record awal.

Tes penutup: fault penulisan admission dan fault penulisan running harus berakhir failed/ditolak dengan alasan jelas; worker tidak hidup, pipeline tidak dimulai jika catatan awal gagal, dan job berikutnya dapat diterima setelah cleanup. Catatan awal normal dan boot recovery yang sekarang lulus harus tetap dipertahankan.

Catatan akurasi laporan: pemanggilan persistensi yang terlihat saat review berada pada admission, running, cancellation, dan finalisasi. Klaim “setiap checkpoint” belum didukung hook persistensi di checkpoint pipeline. Penambahan persistensi pada setiap checkpoint tidak diwajibkan untuk menutup fault di atas; yang wajib adalah record awal dan lifecycle akhir yang jujur.

## B-04 — P2, masih terbuka: file render terputus dianggap hasil sukses

Lokasi:
- [web_app.py:476](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:476)
- [web_app.py:481](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:481)
- [web_app.py:512](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:512)
- [web_app.py:517](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/web_app.py:517)
- [local/clipper.py:295](C:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/clipper.py:295)

Handler cancel/timeout memindai `short_*.mp4` dan menganggap semua file sebagai `valid_shorts`. Keberadaan file tidak membuktikan bahwa render selesai. FFmpeg dapat sudah membuat output yang belum lengkap saat dihentikan; file `.silent.mp4` juga memakai prefix yang cocok dengan glob itu.

Probe membiarkan file output klip pertama yang tidak lengkap, lalu memicu cancellation melalui konteks worker. Hasilnya:

```text
status memory: partial
status disk: partial
stats.success: 1
verify_rendered_video(file): RuntimeError
```

Objek klip hasil pemindaian juga hanya membawa filename/URL/folder, tanpa `clip_index`, In/Out, judul/hook, dan konteks sumber/transkrip. Ini tidak memenuhi klaim retensi seluruh metadata klip valid. Perbaikan daftar benar-benar kosong dan alasan timeout sudah lulus; yang tersisa adalah definisi “klip sukses” saat render terputus.

Perbaikan minimum: retensikan daftar klip yang benar-benar telah selesai beserta metadata lengkapnya dari pipeline, bukan merekonstruksi sukses dari glob. Bila recovery dari disk diperlukan, hanya terima nama kanonikal dan verifikasi media/durasi sebelum memasukkannya sebagai sukses. Jangan hitung klip yang masih ditulis atau intermediate silent/cut. Nol klip selesai harus canceled/timeout sesuai penyebab; satu klip selesai tetap partial dengan metadata lengkap.

Tes penutup: stop saat render klip pertama sudah membuat file tetapi belum selesai; stop saat klip kedua berlangsung setelah klip pertama sukses; intermediate silent/cut tidak dihitung; media/transkrip/clip_index/timeline klip sukses tetap tersedia untuk editor. Tidak perlu memperluas fitur editorial.

## Status temuan sebelumnya

| ID | Penilaian tindak lanjut |
|---|---|
| B-01 | Ditutup untuk FFmpeg in-flight yang diuji; loop wait berkala dan tes nyata lulus. Tahap call sinkron tetap memiliki batas pembatalan kooperatif. |
| B-02 | Record awal dan recovery normal sudah bekerja; penanganan fault awal masih perlu koreksi. |
| B-03 | Gate sudah ada; pencatatan dua request klip yang sama masih membolehkan delete. |
| B-04 | Empty result dan jenis timeout diperbaiki; retensi file tidak lengkap masih keliru. |
| B-05 | Checkpoint antar-tahap API ditambahkan; jalur Gemini lokal gagal import/signature. |
| B-06 | Diterima untuk kontrak UI yang diuji; tujuh skenario Chrome lulus, dengan batas simulasi dijelaskan di atas. |
| B-07 | Bug patch concurrency ditutup; suite penuh 57 tes berjalan stabil pada review ini. |

## Instruksi penutupan yang terbatas

Perbaiki empat residu di atas saja: B-02, B-03, B-04, B-05. Pertahankan B-01/B-06/B-07 dan seluruh 41 baseline Bagian A. Tambahkan regresi untuk empat jalur yang terbukti, jalankan suite penuh dan QA lifecycle, lalu laporkan hasilnya. Jangan mulai Bagian C, NVENC, tracking, ekspor, redesign, atau mengganti arsitektur.

Probe reproduksi: `review_b_followup_probes.py` di folder laporan ini. Probe tidak mengubah source proyek, memakai output sementara, dan membersihkan thread/fixture yang dibuatnya.
