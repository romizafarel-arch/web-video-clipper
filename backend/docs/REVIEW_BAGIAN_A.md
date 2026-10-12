# Review independen Bagian A — ShortsStudio

Tanggal: 28 September 2026.
Checkout yang dinilai: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.
Branch: `main`; HEAD: `de07f3a94a9ef0c4c55376cfa118141de62a3d43`; implementasi aplikasi web dan tes masih merupakan perubahan lokal yang belum di-commit.

Checkout ini berbeda dari `C:\Users\ASUS\.gemini\antigravity\scratch\AI-Youtube-Shorts-Generator`. Temuan awal sebelum lokasi diklarifikasi berasal dari checkout lama dan tidak dipakai untuk menilai implementasi baru.

## Keputusan

Bagian A belum siap dinyatakan selesai. Perbaikan dasar memang ada dan suite 25/25 lulus, tetapi kontrak waktu preview dan konsistensi commit video/subtitle/metadata masih bermasalah. Perbaiki temuan P1 sebelum melanjutkan ke Bagian B.

Arsitektur minimal yang sudah dipilih masuk akal untuk aplikasi pribadi: Flask satu proses, staging di direktori sesi yang sama, dan lock per klip. Tidak diperlukan perubahan framework. Tambahkan konsistensi metadata per sesi, origin waktu klip yang tidak berubah selama editing, serta verifikasi media yang nyata.

## Metode dan batas verifikasi

- Membaca laporan yang diberikan sebagai klaim untuk diverifikasi, bukan sebagai instruksi eksekusi.
- Membaca implementasi backend, frontend editor, renderer, dan seluruh tes pada checkout yang diklarifikasi pengguna.
- Suite terbaru: 25/25 lulus dalam 0,645 detik pada pemeriksaan ini.
- Tes dijalankan dengan direktori output sementara dan bytecode Python dinonaktifkan. Tidak mengubah kode, konfigurasi, atau video pengguna pada checkout tersebut.
- Pengujian tambahan backend memakai renderer mock, fixture sementara, dan fault injection. Ini memeriksa logika commit serta error handling, bukan kualitas encode nyata.
- Pengujian timeline mengeksekusi bagian JavaScript editor yang sebenarnya di Node VM dengan elemen/player stub. Bukan pengujian browser atau playback video nyata.
- Endpoint sumber juga diuji melalui Flask test client dengan Range request.
- Chrome QA, tampilan mobile, serta encode FFmpeg tidak dijalankan ulang pada review ini. FFmpeg/FFprobe tidak ditemukan pada PATH sesi ini.

## Status lima syarat

| Syarat | Status | Penilaian |
|---|---|---|
| Identitas klip Riwayat | Berhasil pada kasus normal; validasi belum lengkap | Indeks 1/2/3 tersedia dan edit klip 2 menjaga klip 1. Indeks pecahan, filename nonkanonik, dan registry kosong masih lolos. |
| Timeline sumber vs klip | Belum memenuhi | Mapping pertama benar, tetapi offset berubah setelah Set In atau edit manual nilai In. |
| Referensi sumber sesi | Memenuhi kasus utama yang diuji | File eksternal berhasil dipakai; tidak ada fallback ke source di root output. Range response 206 benar. Ketahanan terhadap source yang diganti/moved dan metadata rusak masih perlu diuji. |
| Staging, atomisitas, concurrency | Memenuhi sebelum promotion; belum memenuhi keseluruhan commit | Staging unik dan lock klip bekerja. Metadata bersama masih mengalami lost update; kegagalan setelah video dipromosikan tidak menjaga konsistensi. |
| NaN/Infinity dan batas durasi | Sebagian memenuhi | Nonfinite dan boolean timestamp ditolak. Batas media dilewati bila probe gagal, dan transcript duration dipakai tanpa mengecek durasi media aktual. |

## Temuan utama

### A-01 — P1: origin timeline klip berubah mengikuti nilai In yang sedang diedit

Lokasi: `static/js/app.js:1389`, `static/js/app.js:1463`, `static/js/app.js:1483`.

`editorBaseStart` seharusnya menunjukkan waktu sumber pada frame pertama dari file klip yang sedang diputar. Kode memperbaruinya saat nilai In berubah atau setelah tombol Set In ditekan. Mengubah selection In tidak mengubah frame pertama dari file preview, sehingga offset ini tidak boleh ikut berubah.

Bukti menggunakan kode JavaScript asli dengan player stub:

1. Klip mulai pada sumber 605,0 detik; player klip di 12,4 detik.
2. Klik Set In pertama menghasilkan 617,4 detik, benar.
3. Klik Set In lagi tanpa berpindah frame menghasilkan 629,8 detik, keliru.
4. Klik Set Out pada frame yang sama kemudian menghasilkan 642,2 detik.
5. Mengganti In secara manual menjadi 650 dengan player di 10 menghasilkan waktu 660,0; frame sebenarnya masih berada pada sumber 615,0.

Perbaikan: pisahkan origin file preview dari selection In/Out. Origin diambil dari metadata klip tersimpan dan tetap selama file preview itu dipakai. Perbarui origin hanya ketika file/revisi preview benar-benar berubah. Uji klik berulang, edit manual In, pergantian Source/Clip, dan fallback ketika source gagal dimuat.

### A-02 — P1: lock per klip tidak melindungi job JSON yang dipakai bersama

Lokasi: `web_app.py:1184`, `web_app.py:1246`.

Edit klip 1 dan klip 2 memiliki lock berbeda, tetapi keduanya melakukan read-modify-write terhadap file `job_*.json` yang sama. `os.replace` menjaga setiap file JSON utuh, tetapi tidak mencegah perubahan terbaru ditimpa oleh snapshot lama milik request lain.

Bukti: dua request dipaksa membaca snapshot metadata yang sama menggunakan barrier setelah read. Keduanya mengembalikan HTTP 200. Metadata akhir berisi judul `New1`, `Old2`, `Old3`; pembaruan klip 2 hilang, walaupun video klip 2 sudah diganti.

Perbaikan: pertahankan lock per klip selama render, lalu gunakan lock commit per sesi untuk membaca metadata terbaru, menggabungkan perubahan, dan mempublikasikan hasil. Tes tambahan harus mencakup dua klip berbeda pada sesi yang sama. Tes dua request pada klip yang sama sudah ada dan lulus, tetapi tidak mencakup resource metadata bersama.

### A-03 — P1: commit video, VTT, dan metadata tidak konsisten ketika promotion gagal

Lokasi: `web_app.py:1220`, `web_app.py:1265`, `web_app.py:1266`.

Penggantian atomik berlaku per file. Tiga penggantian berurutan bukan transaksi atomik untuk satu revisi klip.

Bukti fault injection:

- Saat penggantian VTT gagal: endpoint mengembalikan 500; video sudah berubah ke `NEW_VIDEO`, subtitle tetap `OLD_VTT_1`, metadata tetap `Old1`. Hasil lama tidak dipertahankan secara keseluruhan.
- Saat penggantian metadata gagal: endpoint tetap mengembalikan 200; video dan VTT sudah baru, metadata tetap `Old1`. Error metadata hanya dicetak sebagai warning.

Perbaikan minimal untuk kegagalan biasa: siapkan dan verifikasi semua artefak sebelum promotion, sediakan rollback teruji, dan jangan laporkan sukses jika commit metadata gagal. Untuk ketahanan saat proses mati di tengah commit, gunakan file video/subtitle ber-revisi yang tidak ditimpa lalu publikasikan satu manifest metadata secara atomik sebagai titik commit. Pembaca mengambil artefak dari revisi manifest yang sama.

Pada Windows, penggantian file dapat gagal karena file sedang dibaca atau dipegang aplikasi lain. Uji kegagalan video replace, VTT replace, metadata replace, dan pembatalan/crash di setiap titik commit. Lock yang ada hanya melindungi satu proses Python; ini memadai jika aplikasi memang berjalan dalam satu proses.

### A-04 — P1: batas durasi dapat dilewati ketika media tidak dapat diprobe

Lokasi: `web_app.py:1091`, `web_app.py:1101`, `web_app.py:1137`.

Jika transcript duration tidak tersedia dan OpenCV gagal membuka file, `source_duration` tetap None dan pemeriksaan batas waktu dilewati. Reproduksi dengan probe yang gagal menunjukkan rentang 100000–100010 detik mencapai renderer dan endpoint mengembalikan 200 dengan renderer mock.

Selain itu, jika transcript duration tersedia, media tidak diprobe. Transcript duration dapat salah, stale, atau berdasarkan timestamp keluaran model; ia tidak membuktikan durasi file video aktual. Dalam pemeriksaan dengan metadata 750 detik, probe yang disiapkan untuk menunjukkan media 2 detik tidak pernah dipanggil dan rentang 500–530 diterima.

Perbaikan: tentukan durasi sumber dari media aktual, simpan bersama identitas file, dan invalidasi ketika file berubah. Jika durasi tidak dapat diverifikasi, hentikan edit dengan pesan yang jelas. Toleransi 0,5 detik boleh digunakan untuk pembulatan, tetapi jangan menyimpan metadata Out yang melampaui durasi video hasil secara diam-diam. Tambahkan kasus start tepat EOF, source diganti di path sama, dan metadata duration salah.

### A-05 — P2: verifikasi staging hanya memeriksa ukuran lebih dari nol

Lokasi: `web_app.py:1215`.

Ukuran positif tidak memastikan MP4 dapat dibuka, memiliki video stream, atau mencakup rentang yang diminta. Reproduksi dengan renderer yang mengembalikan file `NOT_A_VIDEO` diterima sebagai sukses dan menimpa hasil lama.

Perbaikan: probe stream, dimensi, duration, dan kemampuan decode sebelum promotion. Uji hasil nol byte, bytes non-video, MP4 terpotong, dan hasil berdurasi jauh lebih pendek dari selection. Tes mock saat ini menulis string biasa ke file `.mp4`; pertahankan tes state machine tersebut tetapi mock verifier secara eksplisit dan tambahkan satu tes media riil.

### A-06 — P2: subtitle lama tetap dipakai ketika revisi baru tidak menghasilkan VTT

Lokasi: `shorts_generator/local/clipper.py:342`, `web_app.py:1221`, `web_app.py:1224`.

Ketika burn_subtitles=False, renderer tidak membuat VTT baru. Backend mempertahankan VTT lama dan mengembalikan URL-nya. Setelah rentang klip berubah, subtitle lama dapat menunjukkan teks dan timing yang salah.

Bukti: revisi tanpa caption mengembalikan 200 dan URL subtitle, sementara file VTT lama tetap identik.

Perbaikan: tetapkan kebijakan subtitle untuk setiap revisi. Bila subtitle diinginkan, hasilkan VTT dari rentang baru secara independen dari burn-in. Bila subtitle dinonaktifkan, jangan publikasikan URL lama. Gabungkan perubahan ini dengan commit revisi agar video dan subtitle selalu cocok.

### A-07 — P2: validasi identitas masih menerima indeks pecahan dan nama tak sesuai

Lokasi: `web_app.py:1148`, `web_app.py:1166`, `web_app.py:1173`.

Bukti:

- `clip_index: 2.9` diterima sebagai klip 2 karena `int()` memotong desimal.
- `filename: unrelated.mp4` diterima karena penolakan mismatch hanya berlaku jika regex menemukan substring `short_<angka>`.
- Saat registry metadata kosong, request klip 99 diterima dan membuat `short_99.mp4` meskipun file tersebut tidak ada.

Perbaikan: validasi indeks sebagai integer sesuai kontrak, cocokkan filename secara penuh dengan identitas tersimpan, dan izinkan editing hanya pada klip yang dapat diselesaikan dari registry/file yang sah. Untuk kompatibilitas orphan, parse identitas dari nama file yang memang ada, bukan menciptakan klip baru lewat endpoint edit.

### A-08 — P2: membuka ulang editor tanpa refresh memakai data sebelum edit

Lokasi: `static/js/app.js:1144`, `static/js/app.js:1556`.

Handler tombol Edit menutup variabel `item` lama. Setelah save, frontend memperbarui elemen judul dan video, tetapi tidak memperbarui objek data yang dipakai handler. Membuka editor lagi dari kartu yang sama berpotensi mengembalikan judul dan rentang lama. Riwayat yang dimuat ulang dapat menunjukkan data terbaru, sehingga pengujian reload saja tidak menangkap masalah ini.

Bukti: penelusuran statis frontend; belum diuji melalui browser pada review ini.

Perbaikan: simpan data klip terkini dalam satu store, mutasikan objek yang dipakai handler dengan hasil save, atau ambil metadata terbaru ketika membuka editor. Uji save → reopen tanpa refresh → edit kedua → refresh. Gunakan ID revisi unik untuk URL media; timestamp beresolusi satu detik dapat bertabrakan jika dua revisi selesai dalam detik sama.

## Temuan pendukung dan batas arsitektur

- Source resolver sudah memprioritaskan referensi metadata dan tidak mengambil source root output. Pengujian file eksternal dan Range 206 lulus.
- Guard folder memakai `str(path).startswith(str(root))`; prefix string bukan pemeriksaan containment path yang lengkap. Gunakan relasi Path terhadap root agar junction/symlink ke sibling seperti `output_other` ditolak. Ini temuan statis, belum dieksploitasi dalam pengujian.
- Belum ada verifikasi identitas sumber terhadap perubahan file di path yang sama. Pertimbangkan size/mtime bersama referensi sumber dan durasi terverifikasi.
- Metadata dibaca sebelum lock klip didapat. Sumber/selection yang divalidasi bisa menjadi stale saat request menunggu. Ambil ulang keadaan terbaru atau gunakan revision check saat commit.
- ID staging delapan digit hex sudah jauh lebih baik daripada nama tetap. Untuk jaminan alokasi tanpa bentrok, gunakan UUID penuh atau pembuatan file eksklusif.
- Jangan menghapus semua `.tmp_*` secara sembarang saat worker lain aktif. Pemulihan staging sisa crash perlu membedakan revisi aktif dan revisi yang benar-benar ditinggalkan.

## Pengujian tambahan sebelum Bagian B

1. Set In berulang pada frame sama harus menghasilkan nilai yang sama.
2. Edit In manual tidak boleh mengubah origin file klip.
3. Source/Clip switching, source load failure, dan reopening tanpa refresh.
4. Dua request pada klip berbeda harus mempertahankan kedua pembaruan metadata.
5. Kegagalan pada setiap penggantian MP4, VTT, dan JSON menjaga satu revisi yang konsisten dan menghasilkan status jujur.
6. Staging tidak dapat dibaca sebagai video tidak boleh dipromosikan.
7. Probe sumber gagal dan transcript duration salah harus ditangani secara eksplisit.
8. Caption dinonaktifkan atau tidak tersedia tidak boleh memakai VTT revisi lama.
9. Indeks pecahan, filename nonkanonik, registry kosong, dan start tepat EOF ditolak atau ditangani sesuai kontrak.
10. Minimal satu uji browser dengan file nyata yang mulai pada sumber 600+ detik, dua siklus save/reopen, dan verifikasi duration serta subtitle setelah refresh.

Keputusan akhir: tahan kelanjutan ke Bagian B sampai A-01 sampai A-04 diperbaiki dan diuji. A-05 sampai A-08 juga berada dalam ruang lingkup ketepatan editor/perlindungan hasil dan sebaiknya diselesaikan dalam penutupan Bagian A.
