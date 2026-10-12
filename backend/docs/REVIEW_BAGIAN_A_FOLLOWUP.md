# Review independen tindak lanjut Bagian A, ShortsStudio

Tanggal: 28 September 2026.
Checkout yang diperiksa: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.
HEAD: `de07f3a94a9ef0c4c55376cfa118141de62a3d43`, branch `main`, working tree belum di-commit.
Keputusan: **belum selesai penuh; tahan Bagian B sampai sisa koreksi Bagian A diverifikasi.**

Ini adalah review kode dan pengujian independen, bukan penerimaan berdasarkan laporan agen. Tidak ada kode, konfigurasi, atau media proyek yang diubah oleh reviewer.

## Hasil verifikasi

- Suite proyek dijalankan ulang dengan venv checkout utama: **33/33 lulus, 1,140 detik**. Pengujian tambahan juga dijalankan dengan venv yang sama dan mempertahankan semua reproduksi di bawah. Sebelumnya suite juga lulus dengan interpreter venv scratch (1,293 detik). Modul aplikasi dan tes selalu berasal dari checkout utama di atas. Output diarahkan ke direktori sementara sebelum aplikasi diimpor, menggunakan `-B` agar tidak menulis bytecode proyek.
- Pengujian endpoint tambahan menggunakan Flask test client, fault injection, dan fixture di direktori sementara.
- Barrier pada renderer memastikan dua permintaan edit klip berbeda benar-benar tumpang tindih sebelum commit. Keduanya HTTP 200 dan kedua judul tersimpan. Session lock bekerja untuk dua writer editorial dalam satu proses.
- Logika editor dari `static/js/app.js` dijalankan melalui Node VM dengan stub DOM/player: Set In berulang, input manual, mode sumber, fallback sumber gagal, save dan reopen. Ini pengujian JavaScript aplikasi, bukan pengujian browser nyata.
- Verifier diuji melalui endpoint dengan video MP4 riil yang dihasilkan OpenCV: sumber 10 detik, hasil staging 2 detik untuk permintaan 8 detik. Probe dan verifier aplikasi tidak di-mock pada kasus ini; renderer diganti agar mengembalikan hasil pendek tersebut.
- Script CDP dan screenshot QA agen diperiksa. Chrome/CDP dan encoding FFmpeg end-to-end tidak dijalankan ulang oleh reviewer. `ffmpeg` dan `ffprobe` tidak tersedia pada PATH shell review. Klaim QA agen dan pengujian reviewer harus dibedakan.

## Status delapan temuan

| Temuan | Status review | Penjelasan |
|---|---|---|
| A-01, origin preview | Ditutup untuk kontrak yang diuji | Origin terpisah dari selection. Hasil 605 + 12,4 tetap 617,4 meski Set In diulang, In diubah manual, atau sumber gagal lalu fallback ke klip. |
| A-02, lost update metadata | Ditutup dalam Flask single-process | Session lock melindungi fresh read dan commit. Tes overlap dua klip mempertahankan kedua perubahan. |
| A-03, perlindungan promotion | **Belum ditutup** | Rollback satu kegagalan berhasil, tetapi rollback gagal menghilangkan cadangan; artefak tanpa versi lama juga tidak dihapus saat commit gagal. |
| A-04, batas durasi aktual | Sebagian | Probe wajib dan metadata transkrip tidak lagi menjadi otoritas. Toleransi EOF tidak dinormalisasi menjadi rentang yang benar-benar dapat dirender. |
| A-05, verifikasi media | **Sebagian** | Menolak teks korup dan membaca frame pertama, tetapi hasil 2 detik diterima untuk permintaan 8 detik. Belum membuktikan seluruh rentang hasil utuh. |
| A-06, subtitle usang | **Sebagian** | Jalur normal menghapus VTT. Kegagalan unlink ditelan, HTTP 200 dikembalikan, dan history kembali mengekspos VTT lama. |
| A-07, identitas klip | Ditutup untuk input yang diuji | Indeks pecahan, boolean, nama berbeda, dan klip baru yang tidak terdaftar/tidak ada ditolak. |
| A-08, data setelah edit | Sebagian | Reopen editor sudah benar. Handler Tonton/expand masih menggunakan objek lama; history juga menghilangkan revision URL. |

Resolusi sumber eksternal dan containment folder masih benar untuk alur yang diperiksa. Guard `relative_to` sudah menggantikan pemeriksaan prefix string pada resolver dan editor.

## Temuan yang harus diperbaiki

### 1. P1: rollback gagal menghapus salinan hasil lama terakhir, A-03

Lokasi: `web_app.py:1365-1376` dan `web_app.py:1410-1419`.

Promosi metadata dapat gagal setelah MP4 baru dipasang. Pemulihan MP4/VTT memakai `os.replace` tetapi kegagalannya ditelan dengan `except: pass`. Penanganan error luar kemudian menghapus `.bak_` tanpa memeriksa apakah pemulihan berhasil.

Reproduksi: renderer staging di-mock sukses, penggantian metadata dan pengembalian backup disimulasikan terkena file lock.

```text
HTTP 500
video final = NEW_VIDEO
metadata title = Old
VTT lama = hilang
backup yang tersisa = []
```

Hasil lama tidak sekadar gagal dipulihkan; salinan pemulihannya ikut dihapus. Error 500 tidak mengembalikan keamanan data.

Reproduksi kedua: klip terdaftar tetapi belum memiliki MP4 final, lalu metadata commit gagal. HTTP 500 tetapi MP4 baru tertinggal dengan metadata lama. Reproduksi ketiga: sebelumnya tidak ada VTT, revisi menghasilkan VTT baru, metadata commit gagal. MP4 lama pulih, tetapi VTT baru tertinggal dan dapat dipasangkan dengan MP4 lama oleh history.

Perbaikan minimum:

- Catat keadaan awal dan artefak yang benar-benar sudah dipromosikan.
- Jika sebelumnya file tidak ada, rollback harus menghapus file baru yang telah dipromosikan.
- Jika restore gagal, **jangan hapus backup**. Laporkan kegagalan pemulihan secara eksplisit dan simpan informasi lokasi/revisi pemulihan.
- Jangan tampilkan revisi yang belum commit sebagai hasil sah. Backup dan staging juga harus dikecualikan dari pemindaian riwayat/publikasi.
- Uji failure di setiap tahap MP4/VTT/metadata, termasuk kegagalan pemulihan dan kondisi tanpa artefak lama.

### 2. P1: verifier menerima hasil yang secara fisik lebih pendek daripada selection, A-05

Lokasi: `web_app.py:131-166` dan `web_app.py:1291`.

Verifier hanya meminta durasi minimum tetap 0,4 detik, dimensi/FPS/frame count positif, serta satu frame awal yang dapat didecode. Tidak ada perbandingan dengan `end_time - start_time`.

Reproduksi memakai MP4 riil OpenCV:

```text
Durasi sumber terprobe = 10 detik
Selection diminta = 0 sampai 8 detik
Hasil staging yang disodorkan = 2 detik
HTTP 200
MP4 final terprobe = 2 detik
Metadata = 0 sampai 8 detik
```

Jadi teks korup memang ditolak, tetapi render parsial yang masih memiliki header/frame awal sah tetap dapat mengganti hasil lama.

Perbaikan minimum: verifier menerima expected duration yang sudah dinormalisasi; bandingkan durasi fisik dengan toleransi wajar berbasis frame/encoding dan pastikan bagian mendekati akhir juga dapat didecode. Pemeriksaan satu frame awal tidak membuktikan akhir media utuh. Jangan diam-diam melewati verifikasi saat decoder/dependensi tidak tersedia. Tidak perlu NVENC atau framework pengujian baru.

### 3. P2: kegagalan menghapus VTT tetap melaporkan sukses dan history menautkan subtitle usang, A-06

Lokasi: `web_app.py:1354-1360` dan `web_app.py:923-934`.

Reproduksi: VTT lama ada, revisi tanpa subtitle, `Path.unlink(short_01.vtt)` disimulasikan gagal karena file lock.

```text
HTTP 200
video = NEW_VIDEO
metadata title = New
response.clip.vtt_url = null
VTT disk = OLD_VTT
history.vtt_url = /output/<session>/short_01.vtt
```

Kebijakan subtitle hanya benar saat penghapusan berhasil. Scan history menentukan ketersediaan subtitle dari file di disk sehingga membatalkan keputusan metadata revisi.

Perbaikan minimum: kegagalan penghapusan wajib masuk jalur transaksi/rollback dan tidak boleh ditelan, atau gunakan publikasi revision yang tidak lagi mereferensikan artefak lama. History dan player harus menghormati kebijakan/revisi yang berhasil commit. Uji VTT terkunci dan pembacaan history setelah gagal maupun sukses.

### 4. P2: toleransi EOF tidak dinormalisasi sebelum rendering, A-04

Lokasi: `web_app.py:1183-1184`, `web_app.py:1243-1247`, dan metadata `web_app.py:1314-1315`.

Dengan probe sumber 100 detik, permintaan 99,8 sampai 100,4 diterima: metadata mencatat 0,6 detik, sedangkan hanya 0,2 detik tersisa pada sumber. Reproduksi penerimaan endpoint menggunakan renderer/verifier mock, bukan bukti hasil encode riil pada EOF.

Toleransi 0,5 detik bisa dipakai untuk mengatasi pembulatan probe, tetapi tidak boleh menghasilkan metadata di luar rentang fisik tanpa normalisasi. Clamp Out ke durasi sumber atau tolak; setelah clamp, validasi ulang minimum durasi. Gunakan rentang efektif yang sama untuk render, verifier, response, dan metadata. Probe OpenCV yang menghitung `frame_count / fps` belum diuji terhadap semua variasi media pengguna; jangan menyebutnya ground truth universal.

### 5. P2: state terbaru belum dipakai seluruh pemutar/tautan, A-08

Lokasi: `static/js/app.js:1143`, `static/js/app.js:905-906`, `static/js/app.js:1562-1597`, dan `web_app.py:929-941`.

Editor membaca `card._clipData` sehingga reopen kini benar. Namun handler Tonton masih menutup objek `item` awal; expand hasil menutup `s`/`videoSrc` awal. Sesudah save, `_clipData` berubah tetapi objek closure tersebut tidak berubah.

Eksekusi closure JavaScript aktual sesudah save:

```text
card._clipData.title = New
card._clipData.vtt_url = null
Tonton menggunakan title = Old, url = /old, vtt = /old.vtt
```

Update video kartu juga tidak memperbarui/menghapus elemen `<track>` yang sudah ada. Selain itu `/api/history` membangun ulang URL tanpa `rev_id`, sehingga revision URL yang disimpan hilang saat reload.

Perbaikan minimum: semua handler preview membaca data kartu terbaru pada saat klik; sinkronkan track subtitle dan tautan VTT; history mengembalikan revisi/URL untuk MP4 dan VTT yang sudah commit. Uji save tanpa subtitle lalu Tonton/expand tanpa refresh, save dengan subtitle baru, serta refresh dan buka mode klip.

## Arsitektur dan batas jaminan

- Memisahkan `clipOriginStart` dari selection adalah solusi tepat dan cukup sederhana. Origin harus selalu terkait file/revisi media yang benar-benar dimuat.
- Per-clip render lock plus per-session commit lock tepat untuk alat Flask satu proses. Tidak perlu database atau lock lintas proses untuk scope tersebut. Ini belum menjamin koordinasi dengan delete session atau writer pipeline lain; itu perlu diperhatikan saat Bagian B membahas lifecycle.
- Beberapa `os.replace` berurutan **bukan satu transaksi atomik** MP4 + VTT + JSON. Session lock saat ini melindungi writer editorial, bukan pembaca history/media. Pembaca bisa melihat fase antara promosi file dan metadata.
- Backup/rollback dapat memberi perlindungan terhadap error yang tertangkap, tetapi tidak memberi jaminan pemulihan otomatis jika proses mati/listrik putus di antara promosi. Saat ini tidak ada journal/recovery startup yang membuktikan jaminan itu.
- Untuk scope alat pribadi, perbaiki exception safety minimum di atas dan nyatakan batas crash recovery dengan jujur. Jika konsistensi pembaca dan crash merupakan syarat keras, simpan artefak revisi immutable dan gunakan satu manifest atomik sebagai titik publikasi. Itu pilihan bersyarat, bukan keharusan menambah framework.

## Kekuatan dan kelemahan bukti QA agen

Yang terbukti: 33 tes dapat dijalankan dan lulus; script browser menguji angka origin 605 + 12,4, dua save, dan reopen. Screenshot memang ada dan menampilkan revisi kedua.

Yang belum cukup untuk klaim lulus penuh:

- `test_timeline_preview_origin_stability` hanya menghitung angka Python, tidak memanggil JavaScript aplikasi. Test Node VM independen menutup sebagian kesenjangan ini.
- Unit rollback hanya menyuntik kegagalan metadata dengan pemulihan backup yang tetap berhasil. Belum mencakup failed restore, newly created MP4/VTT, dan failure unlink VTT.
- Test media valid membuktikan file 2 detik bisa dibuka; belum membuktikan render sesuai rentang 8/20/30 detik atau bagian akhirnya utuh.
- `tests/browser_qa.js:320-327` mencari `<track>` di history card. HTML history thumbnail memang tidak membuat `<track>` bahkan ketika VTT tersedia, sehingga assertion tersebut tidak membuktikan eliminasi stale subtitle. Script tidak memeriksa VTT disk. Unit test jalur normal memeriksa disk, tetapi tidak kondisi file lock.
- Pengujian mobile hanya memeriksa `document.documentElement.scrollWidth <= innerWidth` ketika history terbuka. Screenshot `docs/screenshot_qa_mobile_390px.png` dan `docs/screenshot_qa_mobile_320px.png` justru memperlihatkan aksi sesi terpotong di sisi kanan; overflow container yang disembunyikan tidak terdeteksi oleh ukuran dokumen. Editor mobile tidak tampak diuji dalam langkah viewport tersebut.
- Browser QA memakai source `testsrc` sintetis. Itu media video riil secara encoding, tetapi belum representatif untuk footage harian dengan FPS/timestamp/audio bervariasi.
- `tests/run_browser_qa.py` memakai nama fixture tetap dan menghapus `test_source_700s.mp4` pada akhirnya meskipun file itu sebelumnya sudah ada. Jalankan QA hanya dalam direktori/output sementara; jangan biarkan runner menghapus file yang bukan dibuat oleh run tersebut.

## Gerbang penutupan Bagian A

1. Retain/recover backup ketika restore gagal; tanpa artefak lama jangan sisakan hasil revisi gagal; MP4/VTT/metadata tidak boleh dinyatakan sukses jika commit tidak konsisten.
2. Hasil staging pendek/parsial ditolak sebelum menimpa hasil lama. Durasi efektif selection harus sama dengan durasi yang diverifikasi dan metadata.
3. Kegagalan unlink VTT tidak menghasilkan HTTP 200 palsu atau tautan subtitle usang setelah reload.
4. Tonton, expand, track, edit, download, dan history menggunakan revisi terakhir yang commit.
5. Tambahkan regresi bermakna untuk failure di atas, jalankan seluruh suite, dan laporkan mana yang mock, fault injection, media fisik, dan browser.
6. Verifikasi editor dan history pada desktop/390/320, termasuk bounding box/tap controls dalam modal, bukan hanya lebar dokumen. Tidak diperlukan redesign di luar koreksi fungsional.

Sesudah kriteria ini lulus, Bagian A dapat ditutup dalam lingkup single-user/single-process dengan batas crash recovery yang disebutkan. Review ini tidak mengizinkan dimulainya Bagian B sebelum koreksi tersebut selesai.
