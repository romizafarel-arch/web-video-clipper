# Review Independen Video 1 dan Rencana Validasi Video 2

**Keputusan: Video 1 dapat ditutup sebagai validasi fungsional yang lulus dengan catatan editorial. Persiapan Video 2 boleh dilanjutkan.** Tiga MP4 dan VTT benar-benar tersedia dan MP4 lolos decode penuh. Keputusan ini tidak menyatakan semua klip siap publikasi, caption sinkron sempurna, seluruh race condition sudah teruji, atau efisiensi cold/warm end-to-end sudah terbukti.

| Identitas | Nilai |
| --- | --- |
| Tanggal review | 29 September 2026, UTC+07:00 |
| Eksekusi Video 1 | 28 September 2026 |
| Repositori | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator` |
| Branch / HEAD terverifikasi | `main` / `fb3aee9b156dabb8ec1b0b14913f189208507766` |
| Dokumen pelaksana | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\docs\LAPORAN_VALIDASI_VIDEO_1_TALKING_HEAD.md` |
| Acuan | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\docs\VALIDASI_PEMAKAIAN_NYATA.md` |
| Job fallback | `val_fb_ds_9904`, sesi `20260928_223824_val_fb_ds_9904` |
| Status checkout | Tidak ada perubahan berkas terlacak; dokumen validasi dan `output_val_v1/` belum terlacak |
| Lingkup reviewer | Inspeksi metadata/log, hash, FFprobe, decode penuh audio/video, struktur VTT, 18 sampel frame hasil dan 6 frame sumber, serta kode relevan |
| Batas inspeksi | Reviewer tidak mendengar seluruh klip atau menonton semua transisi secara kontinu; penilaian ucapan penuh pelaksana dipisahkan dari temuan independen |
| Tindakan | Tidak menjalankan API, re-render, mengubah klip, atau mengubah kode produksi |

## 1. Penilaian metodologi dan kesiapan sistem

### 1.1 Hasil audit

| Area | Penilaian | Bukti dan batasnya |
| --- | --- | --- |
| Identitas dan baseline | Memadai untuk pilot | HEAD cocok, berkas terlacak tidak berubah, hash MP4/job cocok dengan laporan |
| Cache | Reuse terbukti untuk sumber ini | Warm, retry, dan fallback memiliki log cache hit; cold menghasilkan transkrip baru. Jumlah reuse adalah tiga setelah cold, bukan tiga reuse pada tiga run awal |
| Penanganan 503 | Memadai untuk melanjutkan validasi | Tiga job Gemini gagal jujur; fallback dipilih lewat konfigurasi dan tidak mengubah produksi. Data tidak membuktikan panjang prompt menyebabkan 503 |
| Fallback | Berhasil pada satu run lengkap | Snapshot memakai transkripsi Gemini dan highlight OpenAI-compatible APMix; 8 kandidat dan 3 keluaran tercatat, `stats.success=3` |
| Admission proses sama | Bukti lebih kuat dan memadai untuk run ini | Summary menyimpan PID 5992, worker tidak hidup, active manager/webapp `null`, memori/disk `completed`. Snapshot ini mendukung slot bebas pada akhir run, bukan pembuktian semua race condition |
| Integritas MP4 | Lulus pemeriksaan independen | Ketiga audio/video didekode penuh dengan FFmpeg `-xerror`, exit 0, stderr kosong; durasi sesuai seleksi dalam pembulatan frame |
| VTT | Lulus pemeriksaan struktur dasar | Header valid, cue terurut dan dalam durasi dengan toleransi satu frame; bukan uji render VTT di browser atau akurasi ucapan |
| Kualitas visual | Lulus sebagai draf, dengan temuan crop | Teks ASS terbaca pada sampel, tetapi sejumlah angka benchmark/nama produk/harga hilang akibat crop |
| Sinkronisasi dan publikasi | Belum layak disahkan secara menyeluruh | Tidak ada pengukuran alignment ucapan; kesiapan publikasi pelaksana perlu mempertimbangkan temuan crop dan konteks |
| Benchmark efisiensi | Belum selesai dalam lingkup cold/warm lengkap | Hanya satu run selesai, memakai provider highlight yang berbeda dari tiga run gagal |

Metodologi sudah cukup kuat untuk penutupan pilot fungsional dan memulai kategori video berikutnya. Untuk label QA menyeluruh, pisahkan pemeriksaan decode dari kualitas editorial, dokumentasikan pengukuran caption/A/V sync, dan batasi klaim lifecycle pada skenario yang benar-benar diamati. Catatan ini tidak membuka kembali Bagian A–C.

### 1.2 Pemeriksaan fisik independen

| Media | Seleksi sumber | Durasi container | Video / audio | VTT | Decode penuh |
| --- | --- | --- | --- | --- | --- |
| `short_01.mp4` | 20,3–72,3 s, target 52,0 s | 51,96 s; selisih −0,04 s | H.264, 360 × 640, 25 fps; AAC, 44.100 Hz stereo | 30 cue, akhir 51,700 s | Exit 0 |
| `short_02.mp4` | 168,4–223,6 s, target 55,2 s | 55,20 s | Format sama | 32 cue, akhir 54,900 s | Exit 0 |
| `short_03.mp4` | 380,2–440,5 s, target 60,3 s | 60,30 s; video stream 60,28 s | Format sama | 33 cue, akhir 60,300 s | Exit 0 |

Rasio 360:640 tepat 9:16. Selisih durasi audio/video di ujung stream adalah sekitar 17 ms pada klip 1, 0 ms klip 2, dan 20 ms klip 3. Itu bukan bukti lip-sync sempurna di sepanjang klip; FFprobe dan decode tidak mengukur kecocokan gerak bibir terhadap ucapan.

Klip 3 melewati sasaran pengujian maksimum 60 detik sebesar 0,30 detik. Catat sebagai deviasi sasaran editorial; render tetap sesuai seleksi 60,3 detik. Jika durasi maksimum 60 detik harus ketat, pilih batas akhir alami yang menghasilkan durasi tidak melebihi 60 detik, bukan sekadar menghapus 0,30 detik secara buta. Sasaran ini bukan pernyataan batas durasi suatu platform.

### 1.3 Koreksi profiling dan klaim laporan

| Metrik fallback | Rekonstruksi yang didukung log |
| --- | --- |
| Cache siap | Elapsed 0,113 s sejak awal harness; waktu baca cache eksklusif belum terukur. Selisih 0,096 s sejak log ingest juga belum sama dengan durasi fungsi cache |
| Klasifikasi | 37,257 − 1,511 = 35,746 s |
| Ranking hingga log crop | 308,450 − 37,258 = 271,192 s; mencakup parsing/persiapan yang terjadi sebelum log crop |
| Jumlah dua interval panggilan model | 306,938 s |
| Tahap highlight keseluruhan | 308,450 − 0,113 = 308,337 s, termasuk persiapan sebelum panggilan pertama |
| Klip 1 hingga klip berikut dimulai | 380,945 − 308,451 = 72,494 s |
| Klip 2 hingga klip berikut dimulai | 460,238 − 380,945 = 79,293 s |
| Klip 3 sampai akhir worker | 104,779329 s, termasuk finalisasi; bukan waktu encode eksklusif |
| Crop dimulai sampai akhir worker | Sekitar 256,567 s, termasuk finalisasi. Angka 256,298 s/104,511 s pelaksana tidak memiliki batas akhir terpisah pada log yang tersedia |
| Total worker / harness | 565,02 s / 565,0352078 s, sekitar 9 menit 25 detik |

`stage_markers.crop_and_render.end=460,238` menunjuk awal klip ketiga, bukan akhir render. Gunakan event log beserta waktu akhir worker untuk interval yang benar, dan beri label gabungan ketika encode/verifikasi/finalisasi belum terpisah.

Ranking sendiri menghabiskan sekitar 48% waktu job ini. Crop/render/finalisasi juga besar. Data mendukung dua area profiling berikutnya; satu hasil ini belum menentukan manfaat NVENC atau bahwa provider alternatif lebih cepat.

Tagihan aktual tetap **Belum terukur**. Respons 503 tidak cukup untuk menyatakan gratis atau token billing nol; nama model `free` tidak membuktikan biaya akun nol. Sembilan inferensi logis pada empat run tidak otomatis sama dengan sembilan request HTTP.

Versi interpreter run PID 5992 tidak disimpan pada summary. Saat review, interpreter `venv` menunjukkan Python 3.11.9 dan OpenCV 4.14.0. Klaim Python 3.12/OpenCV 4.10 dalam laporan belum didukung artefak runtime; catat versi dari proses pelaksana pada Video 2.

## 2. Evaluasi editorial dan penanganan in-point

### 2.1 Temuan visual yang memengaruhi kesiapan publikasi

| Klip | Temuan reviewer | Implikasi dan tindakan |
| --- | --- | --- |
| 1 | Presenter dan subtitle terlihat baik pada beberapa sampel; awal berupa B-roll laptop sebagaimana sumber, bukan wajah sepanjang klip | Paling sedikit catatan visual pada sampel. Label Siap Dipakai tetap memerlukan pemeriksaan dengar/tonton penuh dari pelaksana |
| 2 | Pembuka caption dimulai “SERIES 3 DAN AMAN”. Pada 0,5/2,5 s, beberapa label baterai pada sumber terpotong; pada 27,6 s, layar/game yang terlihat jelas pada sumber berada di tepi atau hilang dari crop | Bukan hanya perbaikan hook. Jika angka dan layar benchmark adalah bukti utama, perlu mempertahankan B-roll melalui komposisi lain/editor eksternal. Untuk tujuan itu, kategorikan Perlu Edit Besar; untuk narasi suara dengan bukti visual yang tidak wajib, nilai kembali setelah edit |
| 3 | Wajah dan subtitle tampak terbaca pada sampel, tetapi teks nama produk besar terpotong di 0,5/2,5 s. Poster pada 30,15 s kehilangan label Advan, harga, dan sebagian spesifikasi yang tersedia pada sumber | Label Siap Dipakai tanpa catatan terlalu kuat. Perlu edit visual/konteks produk dan pemeriksaan nama pada caption; durasi 60,30 s juga dicatat |

Crop yang menghilangkan informasi B-roll merupakan masalah kualitas editorial/keterbatasan framing baseline, bukan bukti file korup atau koordinat keluar batas. Video sumber tetap utuh. Shot tanpa wajah tidak memiliki pemahaman semantik produk/diagram dalam algoritme sekarang.

Sampel gambar tidak membuktikan semua transisi bebas jitter. Klaim “framing selalu presisi” perlu dibatasi pada rentang yang diperiksa. Klaim “subtitle sinkron sempurna kata per kata” juga harus diganti dengan hasil penilaian yang benar-benar diukur.

### 2.2 Klip 2: edit manual terlebih dahulu

Transkrip cache menunjukkan segmen 163,4–168,4 s berakhir dengan “...tapi semuanya pakai Intel Core”, lalu segmen 168,4–172,6 s dimulai “Series 3 dan aman...”. Pemilihan In tepat di batas segmen 168,4 s tidak menjamin awal kalimat atau konteks berdiri sendiri.

**Rekomendasi saat ini: perbaiki secara manual lewat editor, tanpa mengubah kode atau mengulang inferensi LLM.**

1. Putar sumber sekitar 165–170 s dan pilih awal frasa yang utuh melalui pendengaran. Angka 167,0 s dari pelaksana merupakan kandidat, bukan batas yang sudah diverifikasi reviewer. Geser 168,4 ke 167,0 adalah 1,4 detik, bukan tepat 1,5 detik.
2. Pertahankan akhir 223,6 s jika kalimat penutup memang selesai. Seleksi 167,0–223,6 s menjadi 56,6 detik, masih dalam sasaran 15–60 detik.
3. Periksa ulang subtitle awal setelah re-render. Baseline memasukkan teks lengkap segmen yang beririsan dengan seleksi dan membagi waktunya merata antar kelompok kata. In yang berada di tengah segmen sebelumnya dapat membawa kata-kata sebelum In ke caption awal, walaupun audio telah dipotong dengan benar.
4. Periksa kembali B-roll benchmark yang terpotong. Perbaikan In saja tidak mengembalikan informasi visual yang hilang. Bila perlu, gunakan editor eksternal untuk memasukkan wide shot/diagram dalam kanvas vertikal.

Jangan otomatis menambahkan pre-roll tetap 1,5 detik untuk semua kandidat. Itu dapat membawa topik sebelumnya, kalimat menggantung lain, atau caption yang salah. Pada iterasi kualitas berikutnya, arahan prompt LLM dapat meminta rentang dari awal frasa/kalimat lengkap sampai jawaban selesai, mempertahankan subjek dan antecedent, serta tidak memakai skor sebagai pengganti konteks. Tetap gunakan review manusia karena batas segmen bukan batas kalimat dan model tidak menjamin timing ucapan.

### 2.3 Subtitle, hook, dan skor

Baseline meminta word timestamp saat transkripsi Gemini, tetapi cache merangkum kata menjadi segmen `start/end/text`. ASS dan VTT kemudian membagi durasi segmen merata antar kelompok kata, dengan ukuran kelompok berbeda. Karena itu, output bukan alignment kata presisi; keberadaan VTT bukan bukti subtitle ASS identik timingnya.

Nama produk perlu dibandingkan dengan ucapan dan visual sumber. Contohnya, source poster memuat Advan Air Neo, sedangkan caption memuat rangkaian “MACBOOK R R ... NEO”; reviewer tidak menetapkan koreksi ucapan tanpa mendengarnya.

`hook_sentence` adalah metadata AI, bukan kalimat yang otomatis terdengar pada tiga detik pertama. Skor 96/95/94 berasal dari output model dan bukan probabilitas viral, metrik retention, atau hasil penonton nyata.

## 3. Checklist dan rencana Video 2: podcast multi-speaker

### 3.1 Lingkup dan persiapan

Pilot berikut mengikuti permintaan baru **5–10 menit**, bukan pengujian ketahanan podcast 10–25 menit dalam rencana awal. Gunakan satu video nyata dengan dua pembicara yang terlihat/dapat dibedakan, percakapan bergantian, dan wide shot jika tersedia. Jika sumber tidak memiliki overlap atau shot change, tandai skenario itu Tidak berlaku; jangan mengarang cakupan.

- [ ] Tetapkan satu file lokal tetap; catat hash, size, mtime, durasi, resolusi/fps, audio track, dan bahasa.
- [ ] Pilih sumber dengan wajah/subjek dan suara yang jelas; pertahankan sumber asli untuk membandingkan kehilangan detail pada hasil.
- [ ] Catat sumber, target platform/tujuan klip, dua pembicara A/B, dan kualitas audio awal. Suara sulit dipahami pada sumber tidak otomatis menjadi defect transkripsi.
- [ ] Tetapkan batas API/attempts yang sudah disetujui dan sisa penggunaannya. Satu job bisa melibatkan beberapa inferensi/attempts.
- [ ] Pertahankan baseline dan artefak Video 1. Pisahkan output/cache Video 2 dari Video 1, tanpa menghapus cache yang ada.
- [ ] Jalankan satu cold run Video 2 dengan target 3 klip, sasaran 15–60 detik, Auto 9:16, dan subtitle. Warm run tambahan tidak diperlukan untuk pilot ini.
- [ ] Catat versi proses, PID, konfigurasi, Job ID, log, dan hasil pemeriksaan lifecycle dari manager yang sama.

### 3.2 Provider/model yang direkomendasikan

Gunakan **Gemini `gemini-3.5-transcribe` untuk transkripsi dan APMix `deepseek-v4-flash-free` untuk highlight**, dengan bahasa mengikuti sumber. Kombinasi tersebut telah menyelesaikan Video 1, sehingga sesuai untuk melanjutkan pengujian konten. Ini merupakan rekomendasi berdasarkan satu run sukses, bukan jaminan ketersediaan, diarization, biaya nol, atau latensi cepat.

APMix menggunakan endpoint OpenAI-compatible yang sudah didukung aplikasi. Pertahankan ID yang benar-benar berhasil pada akun; katalog publik bukan pengganti bukti akses akun. [Dokumentasi APMix](https://apmix.ai/docs)

Tidak perlu memulai pilot Podcast dengan pengulangan Gemini Flash yang gagal pada Video 1. Pengujian ulang Gemini dapat dijadwalkan terpisah bila tujuan pengujiannya ketersediaan provider. Jangan mengubah provider/model di tengah job atau menggabungkan hasil model berbeda dalam satu label benchmark.

### 3.3 Strategi framing dan batas kemampuan

Kode Auto memakai wajah terbesar yang terdeteksi, dengan smoothing. Ia tidak mengaitkan crop dengan suara pembicara aktif dan tidak memiliki mode otomatis untuk mempertahankan dua pembicara dalam layout vertikal.

| Skenario | Yang dievaluasi | Interpretasi |
| --- | --- | --- |
| Satu orang berbicara, dua wajah terlihat | Wajah mana yang dipilih, durasi pembicara terdengar tidak terlihat, crop wajah/gesture | Tidak mengikuti pembicara aktif adalah keterbatasan fitur; dampaknya tetap menurunkan kualitas editorial |
| Pergantian pembicara pada wide shot | Pergeseran crop, waktu pembicara baru terlihat, jitter, stale focus | Catat hasil aktual; jangan mengklaim speaker tracking berdasarkan deteksi wajah |
| Camera cut / close-up | Adaptasi setelah cut, apakah crop menyimpang sebelum kembali, informasi yang hilang | Bandingkan dengan sumber pada waktu yang sama |
| Dua orang bicara bersamaan | Apakah konteks percakapan dan wajah penting tetap dapat dipahami | Pemaksaan satu wajah dapat menjadi kelemahan editorial meskipun file valid |
| Tidak ada wajah / B-roll | Apakah produk, tangan, diagram, dan teks sumber tetap terlihat | Tindak lanjuti kehilangan informasi seperti Video 1; bukan sekadar menilai wajah |

Gunakan sumber/wide shot sebagai kontrol visual. UI baseline menyediakan rasio 9:16, 1:1, dan 16:9; “wide 16:9” bukan layout dua orang di dalam kanvas 9:16. Untuk publikasi vertikal, wide shot dapat dimasukkan sebagai inset/letterbox atau layout dua pembicara memakai editor eksternal. Jangan menyebut pilihan itu fitur otomatis aplikasi sekarang, dan jangan menambah implementasinya selama validasi.

### 3.4 Metrik khusus podcast

| Area | Metode dan pencatatan | Status bila tidak didukung |
| --- | --- | --- |
| Pergantian pembicara | Tandai sekitar 10 turn yang tersedia pada sumber/klip. Catat waktu turn, wajah yang terlihat, durasi speaker tidak terlihat, dan ada/tidaknya shot cut | Jika jumlah lebih sedikit, catat jumlah aktual |
| Kualitas crop | Hitung kejadian wajah terpotong, fokus ke pendengar, teks penting hilang, dan perpindahan mencolok; catat detik/rentang dan bandingkan sumber | Salah speaker merupakan keterbatasan/masalah editorial, bukan klaim algoritme speaker tracking gagal |
| Overlap audio | Pilih minimal dua kejadian jika tersedia; periksa kata hilang, ucapan bercampur, kehilangan interupsi, dan konteks respons | Tidak berlaku bila sumber tidak memiliki overlap |
| Akurasi transkrip | Buat referensi manual dari sampel awal/tengah/akhir yang meliputi kedua pembicara. Catat salah/hilang/tambahan kata; WER = (substitusi + delesi + insersi) / kata referensi, dengan aturan normalisasi yang dinyatakan | Jangan menghitung WER dari transkrip model dibanding transkrip model sendiri |
| Atribusi pembicara / diarization | Tandai A/B pada referensi manusia dan nilai apakah pergantian/ucapan masih jelas pada hasil. Cache/output baseline tidak menyimpan speaker ID | Metrik diarization model Tidak didukung / Tidak berlaku; tidak ada DER yang sah untuk output tanpa label speaker |
| Sinkronisasi caption | Periksa sekitar 10 cue per klip di awal/tengah/akhir; catat offset onset/akhir relatif ucapan, arah offset, dan cue yang mendahului/mengikuti turn | Sasaran ±100 ms adalah target editorial yang dipilih, bukan otomatis bug teknis |
| Subtitle saat pergantian | Catat kelompok caption yang mencampur dua pembicara, kepadatan/kecepatan baca, ejaan nama, dan overlap dengan wajah | Jangan menganggap timing merata antar kata sudah akurat |
| A/V sync | Tonton/dengar awal/tengah/akhir, terutama gerak bibir pada close-up; pisahkan salah timing caption dari desync audio-video | Decode dan durasi stream saja tidak mengesahkan lip-sync |
| Konteks dialog | Periksa pertanyaan-jawaban, antecedent kata “dia/itu/ini”, respons/interupsi, dan akhir yang tidak menghilangkan jawaban penting | Hook kuat tidak boleh mengubah makna atau menghapus konteks respons |
| Performa | Catat transkripsi, klasifikasi, ranking, crop/render, verifikasi, total wall time, cache hit/miss, dan usage yang tersedia | Tahap tanpa penanda Belum terukur; biaya tanpa billing Belum terukur |

Diarization berarti penandaan siapa berbicara kapan. Identitas A/B manual untuk evaluasi bukan bukti sistem menghasilkan diarization. Hindari meminta skor akurasi speaker otomatis dari fitur yang belum ada.

### 3.5 Kriteria penutupan pilot Video 2

- [ ] Status akhir memori/disk sesuai hasil; worker selesai dan admission bebas pada proses yang sama.
- [ ] Jumlah hasil dilaporkan jujur. Target tiga MP4/VTT lolos decode penuh dan durasi fisik sesuai seleksi; partial/failed tetap dilaporkan bila terjadi.
- [ ] Semua klip ditonton/didengar penuh dan dibandingkan dengan sumber; skenario turn/overlap/crop dicatat sesuai cakupan aktual.
- [ ] Setiap klip memiliki status Siap Dipakai, Perlu Edit Ringan, Perlu Edit Besar, atau Tidak Layak, beserta alasan, alat, dan waktu perbaikan. Bila belum diperiksa, tetap Belum dinilai.
- [ ] Temuan dipisahkan menjadi bug teknis, masalah kualitas editorial, keterbatasan fitur, dan usulan performa.
- [ ] File keluaran, hash, log, konfigurasi aman, dan bukti penilaian diinventarisasi pada `docs/LAPORAN_VALIDASI_VIDEO_2_PODCAST.md`.

Perbaikan editorial Video 1 dapat dikerjakan terpisah; tidak perlu menunda pilot Podcast sampai semua klip lama dipoles. Tidak ada instruksi untuk memulai Video 3 atau mengubah produksi pada review ini.

## 4. Inventaris bukti independen

| Bukti | Path absolut |
| --- | --- |
| Metadata fallback | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v1\20260928_223824_val_fb_ds_9904\job_val_fb_ds_9904.json` |
| Summary fallback / snapshot PID 5992 | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v1\validation_fallback_summary.json` |
| Klip 1 | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v1\20260928_223824_val_fb_ds_9904\short_01.mp4` |
| Klip 2 | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v1\20260928_223824_val_fb_ds_9904\short_02.mp4` |
| Klip 3 | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v1\20260928_223824_val_fb_ds_9904\short_03.mp4` |
| FFprobe, decode exit, dan pemeriksaan VTT reviewer | `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6\v1_independent_media_checks.json` |
| Sampel klip 1 | `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6\v1_clip_1_samples.png` |
| Sampel klip 2 | `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6\v1_clip_2_samples.png` |
| Sampel klip 3 | `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6\v1_clip_3_samples.png` |
| Frame sumber pembanding | `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6\v1_source_comparison_samples.png` |

| Artefak | SHA-256 yang cocok saat review |
| --- | --- |
| Metadata fallback | `8d908b1067fbed7df09fc2a703153aca2e7258a8d8b5af3933f70c68ee547696` |
| Summary fallback | `884197da956665314c34ec0598a2c6bf05e7dfdee0528f490b4f8ba277ed9c3d` |
| Klip 1 | `c5eff9662d6b0b781e6e264b870275603244e247604ea2377477fe0d6b7cf0f5` |
| Klip 2 | `7d080ff3e58fe255284e0221a6fc7aa233de66a3a7d28f46c57a5223b0cc420a` |
| Klip 3 | `fc59380e39ef07ca25e1e33bf0752d75615db6f2c02a2bfd258f730b935da300` |
| Laporan pelaksana, dipertahankan sebagai sumber | `d5280a0e1b3d3c633f9ec669cb126ad00816c7e0500b26638ba6c4765307c63b` |

Laporan pelaksana tidak ditimpa oleh reviewer. Koreksi dan batas kesimpulannya dicatat di dokumen independen ini. Tidak ada pengujian berbayar baru atau perubahan pada baseline.
