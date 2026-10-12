# Review Runner dan Pre-flight Video 2 Podcast

**Keputusan: isolasi direktori dan kebijakan B/B bekerja pada pemeriksaan independen. Runner belum menegakkan batas satu transkripsi dan dua highlight. Tambahkan guard jumlah inferensi pada harness sebelum menjalankan job berbayar. Bagian A–C tetap ditutup.**

| Identitas | Nilai |
| --- | --- |
| Tanggal | 29 September 2026, UTC+07:00 |
| Repositori | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator` |
| HEAD | `fb3aee9b156dabb8ec1b0b14913f189208507766` |
| Runner | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\scratch\run_validation_v2.py` |
| SHA-256 runner | `83517f4aa56bc9a619ed3a13bab9d93df6b35ac578563fa5b185ad79dd60650c` |
| Pre-flight | `C:\Users\ASUS\web-video-clipper\AI-Youtube-Shorts-Generator\output_val_v2\preflight_v2_check.json` |
| SHA-256 pre-flight | `edcd4165f2517e4825cd69cc5bbbc9a4ca472c2324019b151c989ea33c6b3001` |
| Lingkup | Baca kode/artefak dan jalankan probe lokal dengan mock transport; tidak menjalankan cold run, request jaringan, atau API berbayar |
| Perubahan produksi | Tidak ada |

## 1. Bukti yang diterima

- Checksum runner dan pre-flight cocok dengan laporan.
- HEAD tetap baseline dan tidak ada perubahan berkas terlacak. Runner, dokumen, serta direktori validasi merupakan berkas belum terlacak; jangan menyebut seluruh working tree kosong.
- Pengaturan `LOCAL_OUTPUT_DIR` dilakukan sebelum impor aplikasi. Runner menetapkan working directory, binding root output/cache konsisten, dan pre-flight merekam executable serta versi paket/binary.
- Probe independen menggunakan SDK OpenAI asli dengan `httpx.MockTransport` yang mengembalikan 503. Client memiliki `max_retries=0` dan transport menerima tepat satu attempt. Ini lebih kuat daripada pemeriksaan atribut client saja.
- Probe independen melewati fungsi transkripsi produksi dengan File API dan transport inferensi palsu. Model utama gagal; transport palsu menerima satu inferensi `gemini-3.5-transcribe`, fallback tidak mencapai transport, dan cleanup file tetap dipanggil.
- Timer `perf_counter`, timestamp ber-offset, pencatatan log, serta snapshot worker/admission dalam proses yang sama tersedia dalam runner. Belum ada hasil Video 2 untuk membuktikan pelaksanaannya pada job nyata.

Kebijakan B/B tetap sesuai untuk pilot: tidak ada retry SDK OpenAI dan tidak ada perpindahan model transkripsi. Uji ini tidak mengesahkan kelayakan editorial atau kualitas media yang belum diproduksi.

## 2. Temuan yang harus diselesaikan sebelum eksekusi

### V2-R01, P1: batas inferensi belum ditegakkan

Patch pada constructor OpenAI mematikan retry SDK. Patch Gemini mendeteksi dan memblokir prompt fallback. Keduanya tidak memiliki penghitung yang membatasi inferensi per job.

Kode produksi `call_highlight_api` memiliki `MAX_HIGHLIGHT_API_ATTEMPTS=3`. Jika respons HTTP berhasil tetapi JSON kosong/tidak valid, aplikasi mengirim prompt ranking ulang. Retry ini berbeda dari retry SDK.

Probe independen memakai transkrip palsu 480 detik dan respons model `{}`:

| Metrik | Hasil mock |
| --- | --- |
| Panggilan klasifikasi | 1 |
| Panggilan ranking | 3 |
| Total panggilan highlight | 4 |
| Batas highlight yang dinyatakan | 2 |
| Batas dipenuhi | Tidak |
| Jaringan/API berbayar | 0 |

**Koreksi minimum:** pasang guard per job pada harness sebelum pemanggilan inferensi SDK. Izinkan maksimal satu inferensi transkripsi dan dua inferensi APMix. Naikkan penghitung sebelum meneruskan request. Jika batas terlampaui, blokir request sebelum mencapai transport dan keluarkan error yang jelas. Guard harus menghitung panggilan gagal juga, karena kegagalan tidak membuktikan biaya nol.

Tidak perlu mengubah produksi atau menghapus kebijakan retry aplikasi untuk penggunaan umum. Pada pilot ini, guard harness menghentikan retry tambahan. Catat attempted, dispatched, blocked, success, dan failed secara terpisah. File API upload/polling/delete bukan inferensi dan perlu pencatatan terpisah.

Uji guard dengan mock JSON kosong: maksimal dua request highlight mencapai transport; request tambahan diblokir. Uji transkripsi gagal: maksimal satu request model utama mencapai transport dan tidak ada request fallback. Tidak perlu API berbayar atau pengulangan seluruh suite A–C untuk verifikasi ini.

## 3. Penyesuaian bukti dan verifikasi hasil

Ini merupakan penyempurnaan harness/pelaporan, bukan pembukaan kembali audit produksi:

1. `preflight_status` saat ini tidak memasukkan keberadaan dan keberhasilan `-version` FFmpeg/FFprobe ke syarat PASSED. Artefak yang diperiksa memang memuat kedua binary, tetapi peluncuran berikutnya bisa memakai PATH berbeda. Masukkan pemeriksaan binary tersebut ke syarat sebelum API, dan berhenti jika patch kebijakan gagal.
2. `v1_preserved_untouched` hanya memeriksa keberadaan folder, sementara jumlah file dicatat terpisah. Itu bukan bukti byte-level atau bukti tidak pernah diakses. Gunakan label keberadaan/cache inventory, atau bandingkan hash terhadap inventaris sebelumnya jika ingin menyatakan integritas. Pembacaan inventaris sendiri mengakses direktori; hindari klaim mutlak “tidak diakses”.
3. Verifier hasil mencatat durasi fisik dan expected duration, tetapi belum membandingkannya. VTT baru diperiksa header/jumlah cue. Pada laporan hasil, lakukan perbandingan durasi dengan toleransi yang disepakati, periksa cue terurut dan dalam durasi, serta cocokkan metadata menggunakan `clip_index`/filename, bukan hanya urutan list. Decode sukses tidak membuktikan semuanya.

Jangan mengklaim uji transient error atau uji jalur worker penuh hanya berdasarkan getter atribut client atau satu pemanggilan fallback sintetis. Probe reviewer memperkuat bukti B/B; hasil worker Video 2 tetap menunggu eksekusi.

## 4. Sumber yang direkomendasikan

Kandidat spesifik: **DINAMIKA PERTEMANAN ONCE MEKEL & AHMAD DHANI - PODCAST NAIK CLAS**, kanal Authenticity ID. Halaman penerbit menyebut episode bersama Once Mekel dan identitas Soleh Solihun. [Video resmi YouTube](https://www.youtube.com/watch?v=ClMaZqj8jtI)

- Bahasa yang diajukan: `id`, Bahasa Indonesia; konfirmasi dengan mendengar cuplikan sebelum job.
- Episode penuh lebih panjang daripada pilot. Siapkan file lokal 5–10 menit; jangan memberikan URL episode penuh langsung kepada runner. Runner tidak memiliki parameter pemotongan sumber dan akan memproses input penuh.
- Tinjau bagian awal setelah pengantar sebagai calon cuplikan sekitar delapan menit. Pilih batas berdasarkan kalimat/tanya-jawab utuh, bukan menetapkan rentang yang belum didengar sebagai final.
- Pastikan cuplikan mengandung kedua pembicara, beberapa wide shot dua wajah dan beberapa close-up. Jika tidak memenuhi cakupan, pilih rentang lain atau sumber lain sebelum API.
- Reviewer mengonfirmasi identitas video melalui halaman penerbit; belum menonton rentang uji secara penuh. Tidak ada klaim bahwa jumlah turn, overlap, shot, atau kualitas audio cuplikan sudah terverifikasi.
- Catat URL asli, rentang ekstraksi, hash file lokal, durasi fisik, dan offset sumber. Timeline aplikasi mengacu pada file cuplikan mulai detik nol.

Path file lokal final belum tersedia dan tidak boleh dibuat-buat dalam laporan sebagai sumber yang sudah ada.

## 5. Batas eksekusi yang direkomendasikan

| Batas | Kebijakan pilot |
| --- | --- |
| Input | Satu file podcast lokal terverifikasi, 5–10 menit |
| Job | Maksimal satu cold run |
| Model transkripsi | `gemini-3.5-transcribe`, maksimal satu inferensi dispatched |
| Highlight | `deepseek-v4-flash-free`, maksimal dua inferensi dispatched |
| Retry SDK OpenAI | 0 |
| Fallback transkripsi | Dilarang sebelum request dikirim |
| Retry manual / model probe tambahan | Tidak termasuk pilot |
| Klip | Target tiga klip, sasaran 15–60 detik |
| File API | Upload/polling/cleanup dicatat terpisah dari inferensi |
| Biaya/token | Belum terukur bila tidak ada bukti usage/billing |

Ini merupakan rekomendasi batas kuota teknis, bukan angka biaya rupiah. Jumlah inferensi tidak menjamin nilai tagihan tertentu. Jika pengguna memerlukan batas uang, nilai dan cara penegakannya perlu ditetapkan sebelum job. Review ini tidak menjalankan atau memberi otorisasi otomatis kepada proses eksternal untuk memakai kredensial.

Setelah guard inferensi dan pemeriksaan sebelum API terpasang, sumber dipilih, serta batas penggunaan pengguna tersedia, lanjutkan satu run. Jika gagal, simpan status dan bukti lalu berhenti. Bagian A–C dan penutupan fungsional Video 1 tetap berlaku.

## 6. Bukti probe reviewer

Hasil JSON:
`C:\Users\ASUS\.codex\visualizations\2026\09\28\01a0e5fd-90b3-7972-9035-3069a8f936e6\review_v2_harness_probes.json`

Probe dijalankan lewat interpreter `.venv` dengan SDK lokal, mock transport, dan data palsu. Runner dan pre-flight pelaksana tidak ditimpa. Tidak ada model berbayar atau media baru yang diproses.
