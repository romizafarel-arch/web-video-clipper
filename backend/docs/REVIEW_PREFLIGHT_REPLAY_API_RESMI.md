# Review Independen Pre-flight Controlled Replay Video 3 — API Resmi

Tanggal pemeriksaan: 29 September 2026, selesai setelah 20:45 UTC+07:00.  
Repositori: `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator`.  
HEAD: `main` — `bbd2c4de37f2d1ac2960f9a2a663024d8551d66e`.  
Lingkup: penutupan D-01/O-01.a, preservasi, backup, dan kesiapan operasional. Tidak ada inferensi berbayar, upload media, atau perubahan kode produksi dalam review ini.

## 1. Keputusan resmi

**PRE-FLIGHT VERIFIED — STANDBY FOR USER KEY & APPROVAL**, terbatas pada pilot memakai profil provider/model dan endpoint bawaan yang disepakati.

Penolakan endpoint berbahaya yang menjadi mandat O-01.a sudah terbukti. Nominal tarif, aritmetika estimasi, serta pemisahan jumlah request dari batas uang pada D-01 sudah benar. Dokumentasi masih membutuhkan dua pelurusan kecil: jadwal off-peak DeepSeek dan klaim penolakan opsi CLI. Keduanya tidak mengharuskan perombakan runner ataupun membuka ulang Bagian A–C.

Keputusan ini menyatakan kesiapan teknis pilot; tidak memberi izin panggilan berbayar dan tidak menutup validasi audiovisual Video 3. Tidak ditemukan bukti persetujuan pengguna atau salinan pesan konfirmasi terpadu dalam berkas yang diperiksa. Dalam lingkungan reviewer, kedua kunci khusus provider belum tersedia.

Pengujian terbaru: **11/11 tes wrapper lulus dalam 9,449 detik**, exit code 0. Koneksi jaringan diblokir dalam proses uji; respons inferensi disimulasikan. Media pre-flight diperiksa dengan executable lokal. Seluruh output pengujian reviewer disimpan di direktori terpisah, bukan pada riwayat proyek.

Suite penuh 143 tes telah lulus pada review sebelumnya dalam 40,062 detik. Suite penuh tidak diulang dalam review ini karena perubahan yang diperiksa terbatas pada validator endpoint dan dokumentasi. Angka 143 bukan hasil eksekusi baru pada putaran ini.

## 2. Matriks penutupan D-01 dan O-01.a

| Butir | Hasil independen | Keputusan |
| --- | --- | --- |
| Tarif DeepSeek Flash | Miss: USD 0,30 peak / 0,15 off-peak; hit: 0,006 / 0,003; output: 1,20 / 0,60 per 1M token. Cocok dengan halaman resmi yang terindeks saat pemeriksaan. | PASS |
| Tarif GPT-4o-mini | Miss USD 0,15; hit 0,075; output 0,60 per 1M token. Cocok dengan dokumentasi resmi yang dibuka. | PASS |
| Sumber dan tanggal | Tautan sumber resmi dan tanggal 29 September 2026 dicantumkan. | PASS |
| Aritmetika 9.000 input + 1.600 output | OpenAI / DeepSeek off-peak: USD 0,00135 + 0,00096 = 0,00231. DeepSeek peak: USD 0,00270 + 0,00192 = 0,00462. | PASS |
| Token asumsi dan aktual | Asumsi perencanaan diberi label; tidak diklaim sebagai usage nyata. | PASS |
| Jumlah request dan uang | Dokumen menyatakan maksimum 4 request bukan jaminan biaya; runner belum memiliki hard dollar cap; billing aktual belum terukur. | PASS |
| Jadwal tarif DeepSeek | Kalimat off-peak 16:30–08:30 UTC tidak cocok dengan sumber resmi saat pemeriksaan. | Perlu pelurusan dokumentasi |
| Endpoint kanonikal | OpenAI `/v1`, DeepSeek root, dan varian DeepSeek `/v1` diterima. Endpoint silang dan host lain ditolak. | PASS untuk profil pilot |
| Userinfo / kredensial URL | URL HTTPS dengan userinfo ditolak sebelum admission/dispatch; pesan kasus utama tidak mengulang kredensial uji. | PASS |
| Port nonstandar | `:8443` ditolak. | PASS |
| Query / fragment | Query token dan fragment ditolak; probe independen melengkapi kasus fragment yang belum tercantum eksplisit dalam test_09. | PASS |
| Path nonkanonikal | `/unrelated-path` ditolak. | PASS |
| Isolasi kunci | Kunci generik `OPENAI_API_KEY` tidak menjadi fallback; tanpa kunci khusus, eksekusi online ditolak sebelum dispatch. | PASS |
| Suite wrapper | Semua 11 tes lulus; test_09 memuat userinfo, port, query, dan path. | PASS |

Tarif OpenAI bersumber dari [halaman model GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini). Tarif dan jadwal DeepSeek bersumber dari [Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/). Pembukaan langsung halaman DeepSeek gagal pada putaran ini; informasi di atas diperoleh dari isi halaman primer yang dikembalikan indeks pencarian, bukan dari situs pihak ketiga. Tarif perlu diperlakukan sebagai tarif saat pemeriksaan, bukan jaminan tarif masa depan.

### Pelurusan dokumentasi yang konkret

1. Pada `docs/RENCANA_REPLAY_VIDEO_3_API_RESMI.md:58`, ganti jadwal off-peak dengan: **“Menurut sumber resmi saat pemeriksaan, peak berlaku Senin–Jumat pukul 01:00–04:00 dan 06:00–10:00 UTC; waktu lainnya off-peak.”** Alternatif lebih sederhana: hapus jadwal dan rujuk halaman resmi. Jadwal ini memengaruhi pemilihan tarif DeepSeek, bukan aritmetika kedua skenario yang sudah benar.
2. Pada dokumen yang sama, baris 105, ganti klaim penolakan programatik dengan: **“Pada pilot, jalankan endpoint bawaan tanpa `--base-url` dan tanpa `--api-key`; kunci diberikan melalui environment variable lokal. CLI masih menyediakan kedua opsi tersebut, sehingga larangan ini merupakan prosedur pilot.”** Kedua opsi nyata masih didefinisikan di wrapper baris 320–321. Tidak perlu menghapus opsi untuk menutup mandat pilot ini.

Ada satu batas diagnostik tambahan: URL tidak sah berprotokol HTTP atau mengandung APMix yang sekaligus membawa userinfo tetap ditolak, tetapi pemeriksaan awal pada wrapper baris 77–80 mengulang URL mentah di pesan error. Probe dengan penanda kredensial palsu membuktikannya. Artinya, tidak tepat mengklaim seluruh pesan error bebas kredensial untuk setiap input salah. Ini tidak menghambat pilot yang memakai endpoint bawaan; jangan memasukkan kredensial ke URL. Bila kelak sanitasi seluruh input CLI dijadikan syarat, cukup hilangkan interpolasi URL mentah pada dua pesan tersebut.

Catatan pelaporan usage: callable sekarang mengambil `choices[0].message.content` dan tidak menyimpan `response.usage`. Karena itu, jangan menjanjikan token aktual otomatis tercatat hanya karena inferensi sukses. Laporkan “belum terukur” bila tidak ada bukti usage/billing. Catatan ini tidak memperluas pekerjaan menjadi fitur baru.

## 3. Bukti integritas, backup, dan status kunci

### Preservasi

| Kelompok | Jumlah | Hasil SHA-256 |
| --- | ---: | --- |
| Video 1 | 17 | Identik |
| Video 2 | 48 | Identik |
| `.env`, sumber Video 3, fixture STT | 3 | Identik |
| Total terproteksi | **68** | **0 perbedaan** |

Perbandingan memakai snapshot reviewer dari review terdahulu, bukan hanya membandingkan berkas dengan dirinya sendiri. Tiga modul produksi patch transkrip serta kedua harness/runner terproteksi juga cocok dengan referensi pemeriksaan sebelumnya. Semua 27 berkas riwayat Video 3 yang ada sebelum pengujian terbaru tetap identik setelah pengujian. Perbandingan tambahan terhadap 23 berkas riwayat pada snapshot review terdahulu menghasilkan 0 perbedaan.

Working tree memang memiliki perubahan patch yang sebelumnya telah direview serta berkas baru belum di-commit. HEAD masih baseline di atas. “Terpreservasi” berarti cocok dengan snapshot patch yang disahkan, bukan klaim working tree bersih atau seluruh produksi identik dengan Git HEAD.

### Checksum utama

| Berkas | SHA-256 hasil reviewer |
| --- | --- |
| `scratch/run_controlled_replay_v3.py` | `033ac2a90a4b5b98ea1f519f47fa1d12bf5f85943b0cfdd984ee746d50b34f00` |
| `scratch/run_validation_v3.py` | `3b5e4eef614327a7216bfb72a8cd212541b4bf18b830f75b42c8b3e0a6a306b1` |
| `output_val_v3/source_long_v3.mp4` | `d4e1d8bc5d670bbde3f755acaecd1b3d1963eb87d66ee467be657a37b0d1ac24` |
| Fixture `diagnostic_transcript_pre_validation_val_v3_long_72842.json` | `5c0342f33294bd7ae605a76f0e169560c7fe1acfcc7bdd21de3f428aabffade5` |
| Wrapper resmi yang diuji | `8a3c54ae280ef02e550c89275234df28e47d1c351d623f08e69c7197f555c328` |
| `tests/test_v3_official_harness.py` | `dc8206058e4b6812fbaaba8b3155bbfc056b7f42a2f7c673dabcc49ef7cf75c8` |

### Backup summary

Backup `output_val_v3/validation_v3_replay_summary_backup_pre_official_20260929_203208.json`:

- SHA-256: `24a4b6e5cec6b89935dc22ca29a6b0ccba94579f69af4877d9c6eb05f00ca2a6` — cocok dengan laporan.
- Isinya dibandingkan langsung byte per byte dengan summary global saat review: **identik**.
- Nama backup tersebut belum ada pada snapshot review terdahulu.
- Backup lama `validation_v3_replay_summary_backup_pre_lanjutan.json` tetap ada dan hash-nya tidak berubah.

Bukti ini mengonfirmasi adanya salinan baru tanpa menimpa cadangan lama. Backup tersebut merupakan salinan summary sebelum replay resmi, bukan bukti replay resmi sudah berhasil.

### Kunci dan interaksi pengguna

Pemeriksaan reviewer, termasuk setelah memuat konfigurasi lokal aplikasi, menghasilkan hanya boolean:

```json
{"OPENAI_OFFICIAL_API_KEY": false, "DEEPSEEK_API_KEY": false}
```

Tidak ada nilai kunci dicetak, diminta melalui chat, atau dites ke jaringan. Hasil ini berlaku untuk proses reviewer; terminal Antigravity yang berbeda dapat memiliki environment berbeda dan perlu memeriksa booleannya sendiri saat eksekusi.

Dokumen rencana mengungkapkan tidak adanya hard dollar cap secara jelas. Namun, berkas yang tersedia tidak menyertakan transkrip pesan Antigravity yang mengajukan satu pertanyaan terpadu maupun jawaban persetujuannya. **Kepatuhan pengiriman satu pesan dan penerimaan izin: belum dapat diverifikasi.** Klaim dalam laporan tidak cukup untuk menyatakan izin sudah diberikan.

## 4. Kesiapan eksekusi setelah persetujuan

| Batas / perilaku | Bukti | Status kesiapan |
| --- | --- | --- |
| 0 inferensi Gemini STT | Interceptor `Models.generate_content` selalu menolak; test_04 lulus. | Siap |
| 0 upload File API | Interceptor `Files.upload` menolak; test_04 lulus. | Siap |
| Maksimum 4 highlight | Counter memblokir request ke-5 sebelum fungsi transport dipanggil; test_05 lulus. | Siap |
| `max_retries=0` | Patch konstruktor SDK tetap utuh; test_02/test_10 lulus. | Siap |
| Fail-fast tanpa fallback | Error klasifikasi / ranking menghentikan run; test_06/test_07 lulus. | Siap |
| Request cap 600 detik | Timeout SDK dihitung `min(600, sisa_budget - 60)`; test_03 dan probe SDK review terdahulu mendukung. | Siap sebagai batas timeout SDK |
| Shared budget 1.800 detik | Lookup memakai job manager efektif; checkpoint sebelum/sesudah request; test_11 membuktikan timeout sebelum dispatch saat sisa hanya 30 detik. | Siap sebagai budget kooperatif |
| Render MP4 penuh | `skip_render=False` secara default; kandidat diteruskan ke cropper dan verifier media. | Jalur siap; keberhasilan run resmi belum diuji |
| Satu eksekusi | Runner mengeksekusi satu panggilan dan tidak menjadwalkan run ulang sendiri. | Siap; jangan jalankan invocation kedua tanpa izin baru |

Timeout SDK bukan janji pemutusan paksa seluruh proses persis pada detik ke-600; shared budget diperiksa pada checkpoint, bukan watchdog terpisah. Ini batas implementasi yang sudah ada, bukan klaim pagu waktu atau uang absolut.

Setelah pengguna memilih provider/model, mengonfirmasi kunci lokal tersedia, dan menyetujui maksimum 4 inferensi serta satu invocation dengan pemahaman bahwa hard dollar cap belum ada, pilot boleh dilanjutkan pada endpoint bawaan. Jangan gunakan `--base-url`, `--api-key`, atau `--skip-render` untuk pilot. Mulai sebagai proses Python terpisah, lakukan pemeriksaan hash sebelum/sesudah, lalu laporkan sukses/gagal apa adanya tanpa retry otomatis.

Tidak diperlukan fase persiapan arsitektur baru untuk pilot ini. Dua pelurusan dokumentasi dapat dilakukan singkat sebelum keputusan provider/biaya. Penutupan Video 3 tetap menunggu MP4 nyata, decode, durasi fisik, subtitle ASS/VTT, framing, dan inspeksi audiovisual.

### Inventaris bukti reviewer

Semua berkas berikut berada di `C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6`:

- `review_v3_official_preflight_suite.log`: eksekusi terbaru 11 tes.
- `review_v3_official_preflight_test_result.json`: exit code, preservasi, dan riwayat sebelum/sesudah.
- `review_v3_official_preflight_before.json`: snapshot hash sebelum pengujian terbaru.
- `review_v3_official_preflight_probe_result.json`: penolakan 8 bentuk URL, fragment, batas diagnostik, hash, dan kesetaraan backup.
- `review_v3_official_closing_probe_result.json`: bukti SDK nyata dengan transport simulasi pada review terdahulu. Data penerimaan URL lama dalam berkas ini sudah digantikan hasil probe pre-flight terbaru; data guard/payload tetap relevan karena harness tidak berubah.
- `review_v3_official_closing_suite.log`: suite penuh 143 tes dari review terdahulu.

Tidak ada temuan dalam laporan ini yang menyatakan kualitas editorial atau latensi provider resmi Video 3 sudah terbukti.
