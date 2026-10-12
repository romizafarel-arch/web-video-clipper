# Review independen Video 2: run verifikasi podcast

Tanggal review: 29 September 2026.

Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.

HEAD: `main`, `fb3aee9b156dabb8ec1b0b14913f189208507766`. Dua berkas produksi berubah di working tree; hasil ini menggunakan baseline ditambah patch lokal, bukan baseline murni. Review tidak mengubah kode produksi dan tidak membuat panggilan API.

## Keputusan

**Pipeline dan integritas media: PASS untuk run `val_v2_pod_verify_61609`. Validasi Video 2 secara penuh, termasuk kualitas editorial dan pelaporan seluruh penggunaan API: BELUM PASS.**

Tiga klip benar-benar ada, cocok dengan checksum laporan, dapat didekode penuh, dan durasinya sesuai seleksi. Mekanisme pembentukan segmen terbalik berhasil direproduksi dan patch mengatasi kasus tersebut. Namun, klaim framing, subtitle, keutuhan narasi, dan kepatuhan jumlah run melampaui bukti yang tersedia. Ada juga satu ketidaksesuaian kecil pada patch terhadap larangan durasi fiktif.

Bagian A–C dan Video 1 tidak dibuka kembali. Hasil baru tetap dapat digunakan sebagai draf editorial; koreksi yang diminta tidak memerlukan pengulangan transkripsi atau highlight berbayar.

## 1. Pemeriksaan yang dilakukan

- Membaca diff produksi, runner, tes regresi, laporan, metadata job, diagnostik WordInfo, cache transkrip, dan WebVTT.
- Mengambil helper asli dari AST kode baseline menggunakan `git show`, lalu menjalankannya terhadap payload diagnostik tanpa API. Rekonstruksi tidak memakai salinan algoritme perkiraan dari skrip pelaksana.
- Menjalankan probe parser dan pengelompokan segmen pada data sintetis.
- Mengulang suite proyek: **96 tes, 30,618 detik, OK**, tanpa skip pada eksekusi yang memperoleh akses FFmpeg. Percobaan awal dalam sandbox gagal mengakses executable FFmpeg; itu keterbatasan lingkungan reviewer, bukan regresi produksi.
- Memeriksa ulang FFprobe dan decode penuh video serta audio ketiga MP4 menggunakan FFmpeg `-xerror`: seluruhnya exit 0, stderr kosong.
- Membandingkan 12 frame hasil dengan frame sumber pada waktu yang sesuai. Ini inspeksi frame statis, bukan pemutaran audiovisual menyeluruh.
- Membangkitkan ulang ASS/VTT secara lokal dari cache transkrip dan seleksi yang sama. VTT yang dibangkitkan ulang identik byte demi byte dengan artefak asli.
- Memeriksa checksum cache Video 1 dan artefak cold run pertama: cocok dengan nilai laporan sebelumnya.

## 2. Investigasi Segmen 86: mekanisme terbukti, provenance harus tepat

Payload 1015 kata berasal dari:

`C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2\20260929_125137_val_v2_pod_verify_61097\diagnostic_transcript_pre_validation_val_v2_pod_verify_61097.json`

Metadata diagnostik menyatakan job `val_v2_pod_verify_61097`, tersimpan pukul 12:52:00, bukan job cold run `val_v2_pod_37266` pukul 06:14.

Replay kode baseline yang tepat menghasilkan 130 segmen, termasuk **indeks 86, start 329,8, end 326,0, teks `gitu. Heeh. Heeh.`**. Ini mengonfirmasi kelemahan algoritme lama pada timestamp yang mundur. Replay patch terkini terhadap payload yang sama menghasilkan 138 segmen yang lolos kontrak.

Tetapi ini membuktikan mekanisme menggunakan respons run berikutnya, bukan identitas payload cold run pertama. Kesamaan jumlah kata tidak membuktikan dua respons model identik. Laporan perlu membedakan keduanya.

Label speaker pada raw words yang diperiksa kosong. Lompatan timestamp terbukti; atribusi pembicara A/B dan sebab akustik berupa overlap harus berasal dari inspeksi audio bertimestamp. Timestamp mundur sendiri juga dapat merupakan kesalahan alignment model. Jangan menyatakan seluruh backward jump pasti membuktikan overlap suara.

Diagnostik job 61097 mencatat kegagalan adapter sementara: Word 100 `Kenapa?`, start 51,4 lebih kecil dari previous start 51,8. Job tersebut berhenti karena fallback diblokir. Ini run gagal nyata tambahan yang harus masuk kronologi.

## 3. Review patch produksi

Perbaikan yang tepat:

- Offset yang hilang dibedakan dari nol; NaN, infinity, negatif, dan end yang mendahului start ditolak dengan konteks kata/field.
- Flush dilakukan sebelum menambahkan kata yang memulai rentang lebih awal dari segmen aktif, sehingga rentang tidak berbalik.
- Batas berdasarkan minimum start dan maksimum end mengatasi kata sebelumnya yang berakhir lebih lambat.
- Respons hanya memakai kandidat utama; alternatif tidak digabung seluruhnya.
- Validator cache mempertahankan kondisi lama dan kini menyebut alasan penolakan.

### V2-01 [P2]: durasi minimum buatan masih ada

Lokasi: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\shorts_generator\local\gemini_transcriber.py:384`.

Kode aktual adalah `round(max(seg_start + 0.1, seg_end), 2)`. Ini berbeda dari klaim bahwa end selalu berasal dari `max(end)` kata tanpa durasi fiktif.

Probe satu kata 10,00–10,02 menghasilkan segmen 10,00–10,10. Kata 10,00–10,00 juga diubah menjadi 10,00–10,10. Perbaikan: pertahankan batas yang berasal dari data dan tetapkan perlakuan eksplisit untuk interval nol; jangan membuat end tambahan agar tampak valid. Tambahkan regresi untuk interval pendek dan nol.

Perbandingan offline dengan floor dihilangkan menunjukkan **0 segmen berubah** pada kedua payload nyata 1015 dan 998 kata. Temuan ini tidak membatalkan integritas tiga MP4 saat ini dan koreksinya dapat diuji tanpa API.

### V2-02 [P2]: diagnostik membaca seluruh video ke RAM

Lokasi: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\shorts_generator\local\gemini_transcriber.py:445`.

Hash memakai `hashlib.sha256(Path(media_path).read_bytes())`, sehingga alokasi memori sebanding dengan ukuran sumber. Pada sumber 51 MB saat ini tidak ditemukan kegagalan, tetapi helper baru ini akan dijalankan lagi untuk Video 3 yang lebih panjang. Gunakan pembacaan blok untuk hash, atau helper streaming yang sudah tersedia, dengan checkpoint cancellation bila proses panjang. Tidak perlu perombakan arsitektur.

Catatan tambahan, tidak menjadi alasan mengulang run:

- Python bool diterima sebagai int oleh parser: probe False/True menghasilkan 0–1 detik. Penolakan bool eksplisit akan memperjelas batas input.
- `backward_jump` dibandingkan dengan awal segmen, bukan start kata sebelumnya. Jadi timestamp mundur di dalam rentang segmen masih dapat mempertahankan urutan teks yang tidak kronologis. Patch menjamin rentang valid, bukan diarization atau alignment kata sempurna.
- Pause dibandingkan dengan end kata terakhir; pada overlap panjang, ini bisa memecah segmen padahal kata sebelumnya masih berlangsung. Perlu sasaran kualitas terpisah, bukan klaim bahwa overlap telah sempurna.
- Tes payload nyata bergantung pada artefak `output_val_v2` dan melakukan skip bila tidak ada. Untuk regresi yang dapat dijalankan dari checkout baru, simpan fixture kecil yang disanitasi di direktori tes. Suite 96/96 terkonfirmasi di mesin ini, bukan bukti bahwa artefak tersebut tersedia di clone lain.

## 4. Kepatuhan API dan preservasi

Untuk **job 61609 saja**, snapshot counter mencatat 1 transkripsi, 2 highlight, 0 inferensi diblokir, dan 0 kegagalan SDK. Runner mengunci OpenAI `max_retries=0`, membatasi dispatch highlight, dan memblokir fallback Gemini. Guard berlaku per proses/job dan counter direset setiap run; ini bukan kuota kumulatif seluruh fase.

Kronologi yang tersedia memiliki tiga job:

| Job | Waktu | Hasil | Bukti inferensi |
| --- | --- | --- | --- |
| `val_v2_pod_37266` | 06:14:26–06:14:50 | Failed, kontrak transkrip | Counter tersimpan: 1 transkripsi, 0 highlight |
| `val_v2_pod_verify_61097` | 12:51:37–12:52:02 | Failed, fallback diblokir setelah adapter menolak urutan kata | Respons 1015 WordInfo tersimpan; summary counter per-run tidak ditemukan |
| `val_v2_pod_verify_61609` | 13:00:09–13:08:41 | Completed, 3 klip | Counter tersimpan: 1 transkripsi, 2 highlight |

### V2-03 [P2]: laporan belum mencatat seluruh run dan operasi API secara jujur

Prompt yang diberikan meminta tepat satu run verifikasi. Dua job verifikasi ada di disk. Izin tambahan untuk job 61097 belum terkonfirmasi pada saat review; pertanyaan sudah diajukan kepada pengguna. Jangan menyatakan patuh batas total fase sebelum kronologi, izin, dan konsumsi job tambahan dijelaskan. Jangan mengarang jumlah request yang tidak tersimpan.

Runner menyimpan summary verifikasi pada satu filename tetap, sehingga hasil terbaru dapat menimpa summary verifikasi sebelumnya. Selanjutnya simpan summary per Job ID untuk menjaga jejak audit; pointer ringkasan terbaru boleh tetap ada.

`file_api.upload`/`delete` dihitung **sebelum** pemanggilan SDK, tanpa counter hasil. Cleanup produksi juga menelan exception delete. Dengan bukti yang ada, upload berhasil didukung file ID, tetapi delete hanya terbukti dicoba. Tabel yang menyatakan delete success 1, failed 0 tidak didukung pencatatan aktual. Koreksi label atau tambahkan pencatatan hasil pada runner untuk eksekusi berikutnya; tidak perlu memanggil API ulang hanya untuk membuktikannya.

Hash cache Video 1, audio cache Video 2, metadata cold run pertama, dan summary cold run pertama cocok dengan catatan sebelumnya. Isolasi output/cache yang diperiksa tetap benar. Biaya/token belum terukur tanpa usage/billing evidence; label model mengandung kata `free` tidak menjadi bukti biaya aktual nol.

## 5. Integritas media: PASS

| Klip | Seleksi sumber | Durasi fisik | Delta terhadap seleksi | Decode penuh | VTT |
| --- | --- | --- | --- | --- | --- |
| 1 | 417,6–482,4 s | 64,80 s | 0,00 s | Exit 0 | 37 cue, dalam durasi, tidak overlap |
| 2 | 37,1–85,2 s | 48,08 s | −0,02 s | Exit 0 | 23 cue, dalam durasi, tidak overlap |
| 3 | 110,0–168,6 s | 58,60 s | 0,00 s | Exit 0 | 29 cue, dalam durasi, tidak overlap |

Ketiganya H.264/AAC, 404×720, 25 fps. Rasio mendekati 9:16 sesuai pembulatan dimensi encode. Checksum MP4 dan VTT cocok dengan laporan.

Durasi audio/video yang mirip merupakan bukti panjang stream; itu tidak membuktikan lip-sync atau ketiadaan offset konstan antara suara dan gambar. Reviewer belum mendengar seluruh audio. Keakuratan ucapan, A/V sync perseptual, dan kualitas hook masih memerlukan inspeksi pemutaran.

## 6. Klaim kualitas editorial belum dapat disahkan

### V2-04 [P1 terhadap sign-off editorial]: framing dan keutuhan klip 1 tidak sesuai klaim

Pada klip 1 detik lokal 0,5 dan 5,0, sumber adalah wide shot dua orang tetapi crop menampilkan meja/tengah ruangan; wajah kedua subjek berada di luar bingkai. Pada klip 2 detik lokal 5,0, wajah di shot sumber utuh, sedangkan hasil crop memotongnya pada tepi kanan. Ini bukti inspeksi frame aktual, bukan kesimpulan dari bounding box metadata.

Tidak perlu menggolongkan kegagalan mengikuti pembicara aktif sebagai fitur rusak yang belum dijanjikan. Akan tetapi, pembicara hilang dari pembuka atau wajah terpotong tetap masalah kualitas framing; status keseluruhan “Terpenuhi, tidak ada wajah terpotong” salah.

Klip 1 juga **64,8 detik**, melampaui target evaluasi 15–60 detik. Ini penyimpangan target pengujian, bukan klaim pelanggaran durasi platform. Metadata/WordInfo menunjukkan seleksi berhenti pada 482,4, tepat sebelum frasa 482,4–484,0 `lagu-lagu yang dipakai di event itu.` Cue akhir adalah `ROYALTY KEPADA LMKN ATAS`. Jadi klaim keutuhan narasi memerlukan koreksi; indikasi potongan menggantung kuat berdasarkan transkrip, dengan konfirmasi audio manual tetap diperlukan.

Perbaikan editorial dapat dilakukan pada media yang ada: pilih rentang selesai ≤60 detik, perbaiki pembuka wide shot melalui framing yang sesuai di editor eksternal, dan periksa perubahan shot pada klip 2. Tidak membutuhkan transkripsi/LLM ulang.

### V2-05 [P1 terhadap validitas laporan]: offset ASS/VTT 0 ms bukan hasil pengukuran

Kode ASS menggunakan kelompok target 4 kata, VTT target 5 kata. Regenerasi lokal menghasilkan:

| Klip | Cue ASS yang diregenerasi | Cue VTT asli | Batas cue identik? |
| --- | --- | --- | --- |
| 1 | 42 | 37 | Tidak |
| 2 | 27 | 23 | Tidak |
| 3 | 31 | 29 | Tidak |

Contoh klip 1: ASS membagi rentang 0–4,70 menjadi 0–1,57, 1,57–3,13, 3,13–4,70. VTT membaginya menjadi 0–2,35 dan 2,35–4,70. Jadi klaim seluruh offset identik 0 ms tidak benar. Penggunaan pembagian berbeda sendiri bukan otomatis bug.

ASS asli sudah dihapus setelah render; jumlah ASS di atas adalah hasil regenerasi helper produksi dari input yang sama, bukan subtitle yang diekstrak dari bitstream. VTT regenerasi cocok byte demi byte dengan file aktual, dan fungsi produksi mendukung perbedaan grouping tersebut.

Yang harus diuji untuk sasaran ±100 ms adalah teks yang tampil terhadap ucapan sumber. Membagi rata durasi segmen berdasarkan jumlah kelompok kata tidak membuktikan alignment kata. Durasi stream, cue yang terurut, atau kesamaan sumber data juga tidak membuktikan akurasi ejaan 998 kata.

### Ringkasan tujuh kriteria

| Kriteria | Penilaian independen |
| --- | --- |
| Pergantian pembicara | Dialog ada; daftar turn dan target sekitar 10 pergantian perlu bukti audio/timestamp lintas sampel. Dua baris berurutan dari pembicara sama bukan dua pergantian. |
| Framing | Belum lulus keseluruhan; masalah nyata pada klip 1 dan 2. Sampel klip 3 lebih baik. |
| Overlap/backchannel | Perbaikan rentang waktu teruji; subtitle ketiga hasil tidak overlap. Ketepatan atribusi dan timing overlap akustik belum dinilai manual. |
| Akurasi transkrip | Belum dinilai terhadap audio/ground truth; jumlah kata bukan metrik akurasi. |
| Subtitle sync ±100 ms | Belum terukur terhadap ucapan; klaim ASS/VTT identik dibantah kode dan regenerasi. |
| Lip-sync/A/V sync | Decode dan panjang stream lulus; sinkronisasi perseptual belum dinilai. |
| Keutuhan konteks | Klip 1 memiliki indikasi akhir menggantung; klip 2 dan 3 memerlukan penilaian audio/cerita lengkap. |

Laporan juga belum memberi empat status kesiapan publikasi dan estimasi waktu perbaikan per klip yang diminta rencana. Berdasarkan visual saja: klip 1 memerlukan perbaikan besar framing dan seleksi; klip 2 membutuhkan koreksi crop pada transisi; klip 3 memiliki sampel framing baik tetapi belum dapat diberi label siap publikasi. Estimasi waktu manual belum diukur, sehingga tidak diisi angka rekaan.

## 7. Profiling dan prioritas kecepatan

Interval log run 61609 konsisten dengan total generasi worker 511,079 detik. Transkripsi + pembentukan segmen sekitar 20,435 detik; interval ranking highlight 31,832–299,996 sekitar **268,164 detik**, yaitu **52,5%** total. Seluruh pemrosesan tiga klip sekitar **211,082 detik**, yaitu **41,3%** total.

Interval klip menggabungkan cut, OpenCV, burning subtitle, encode, dan overhead lain. Belum ada pengukuran terpisah OpenCV versus FFmpeg. Interval klip 3 juga mencakup finalisasi worker. Total 511 detik diambil sebelum pemeriksaan FFprobe/decode pasca-job pada runner, jadi bukan total seluruh aktivitas QA.

Jika fase berikutnya membahas kecepatan, ukur dan prioritaskan latensi highlight serta pemrosesan klip berdasarkan angka tersebut. Optimasi encode saja tidak menyelesaikan waktu tunggu LLM 268 detik. Tidak ada perubahan provider atau fitur akselerasi yang dilakukan dalam review ini.

## 8. Penutupan praktis sebelum Video 3

1. Koreksi kecil adapter: hilangkan durasi buatan, tambah regresi interval pendek/nol; untuk sumber panjang, gunakan hashing streaming pada diagnostik. Semua dapat diuji tanpa API dan tanpa mengulang audit A–C.
2. Koreksi laporan: masukkan job 61097, bedakan provenance respons, batasi klaim delete dan akurasi/sync sesuai bukti, serta catat token/biaya sebagai belum terukur bila tidak ada datanya.
3. Tinjau ketiga MP4 yang sudah ada secara audiovisual, isi status kesiapan dan kebutuhan edit, dan catat crop/akhir klip sebagai temuan kualitas nyata. Perbaiki media secara lokal bila ingin menguji hasil setelah edit; simpan versi asli.
4. Tidak perlu run inferensi Video 2 baru untuk menutup temuan ini. Setelah catatan tersebut lengkap, Video 3 dapat digunakan untuk validasi video panjang dengan persetujuan sumber dan batas API tersendiri. Keberhasilan teknis Video 2 tetap diakui walaupun output editorial memerlukan edit.

## 9. Artefak reviewer

Seluruh artefak pemeriksaan berikut berada di:

`C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`

- `review_v2_verification_probes.py`: harness offline pembuktian baseline, parser, media, dan regenerasi subtitle.
- `review_v2_verification_probes.json`: hasil probe, checksum, metadata media, perbandingan floor durasi, dan cue.
- `review_v2_unittest_verified.txt`: eksekusi 96 tes, OK.
- `review_v2_source_clip_01.png`, `review_v2_source_clip_02.png`, `review_v2_source_clip_03.png`: 12 pasangan frame sumber/hasil pada timestamp yang sesuai.
- `review_v2_short_01.ass` sampai `review_v2_short_03.ass`, serta VTT regenerasi: pemeriksaan lokal subtitle. Bukan pengganti artefak asli.

Tidak ada kode produksi, cache Video 1/2, source, MP4, VTT, atau metadata pengguna yang diedit oleh reviewer.
