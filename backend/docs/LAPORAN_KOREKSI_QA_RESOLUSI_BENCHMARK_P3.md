# Laporan Koreksi QA: Resolusi Crop 9:16 Benchmark Prioritas 3

Tanggal: 2026-09-30  
Repositori: `AI-Youtube-Shorts-Generator`  
Target File: `scratch/benchmark_render_optimization.py`  
Laporan Benchmark Terkoreksi: `scratch/render_profiling/benchmark_results/optimization_benchmark_report.json`  
Cadangan Laporan Lama: `scratch/render_profiling/benchmark_results/optimization_benchmark_report_legacy_hardcoded.json`  

---

## 1. Latar Belakang Masalah
Pada pelaporan awal benchmark Prioritas 3, seluruh 4 skenario benchmark menunjukkan status `resolution_match: false`.  
Penyebab ketidakcocokan tersebut adalah nilai `expected_res` pada skrip harness `scratch/benchmark_render_optimization.py` yang ditulis statis/hardcoded:
- `talking_head_v1`: ditulis statis `(404, 720)`.
- `podcast_v2`, `long_video_v3_early`, dan `long_video_v3_late`: ditulis statis `(608, 1080)`.

Pada kenyataannya, file video sumber lokal aktual yang diuji berdimensi:
- `source_NoDG4oewwjg_720p.mp4`: $1280 \times 640$ (rasio 2:1).
- `source_podcast_v2_clip.mp4`: $1280 \times 720$ (rasio 16:9).
- `source_long_v3.mp4`: $1280 \times 720$ (rasio 16:9).

Output render yang dihasilkan oleh pipeline produksi [`shorts_generator/local/clipper.py`](file:///c:/Users/ASUS/web-video-clipper/AI-Youtube-Shorts-Generator/shorts_generator/local/clipper.py) mematuhi rumus pemotongan 9:16 dari tinggi sumber ($src\_h$) dengan pembulatan genap:
$$\text{crop\_h} = src\_h$$
$$\text{crop\_w} = \text{max}(2, \text{int}(src\_h \times 9 / 16) - (\text{int}(src\_h \times 9 / 16) \pmod 2))$$

Sehingga untuk $src\_h = 640$, crop 9:16 genap adalah $360 \times 640$, dan untuk $src\_h = 720$, crop 9:16 genap adalah $404 \times 720$.

---

## 2. Tindakan Koreksi
1. Skrip `scratch/benchmark_render_optimization.py` diperbarui untuk menghitung resolusi crop 9:16 yang diharapkan secara dinamis berdasarkan dimensi sumber aktual (`cv2.CAP_PROP_FRAME_WIDTH`, `cv2.CAP_PROP_FRAME_HEIGHT`) dengan pembulatan ukuran piksel genap (`compute_expected_crop_resolution`).
2. Laporan lama dicadangkan ke `scratch/render_profiling/benchmark_results/optimization_benchmark_report_legacy_hardcoded.json`.
3. Mode verifikasi metadata `--verify-only` dijalankan terhadap file MP4 hasil render yang sudah ada tanpa melakukan render ulang atau mengubah angka durasi performa.
4. Seluruh angka metrik benchmark performa asli (run 1, 2, 3, median, min, max, stdev) dipertahankan 100% tanpa perubahan.

---

## 3. Hasil Pemeriksaan QA Resolusi (4 Skenario)

| Skenario Cuplikan | Dimensi Sumber Aktual | Rumus Harapan 9:16 Genap | Resolusi Render Aktual | Status Kecocokan | Probed Duration | Median Runtime Asli |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **talking_head_v1** | $1280 \times 640$ | $360 \times 640$ | $360 \times 640$ | **MATCH (True)** | 15.000s | 34.241s |
| **podcast_v2** | $1280 \times 720$ | $404 \times 720$ | $404 \times 720$ | **MATCH (True)** | 15.000s | 50.168s |
| **long_video_v3_early** | $1280 \times 720$ | $404 \times 720$ | $404 \times 720$ | **MATCH (True)** | 15.015s | 62.738s |
| **long_video_v3_late** | $1280 \times 720$ | $404 \times 720$ | $404 \times 720$ | **MATCH (True)** | 14.982s | 29.660s |

---

## 4. Kesimpulan QA
- Tidak ada anomali atau deviasi piksel pada pipeline produksi.
- Seluruh 4 klip hasil render MP4 telah terbukti 100% sesuai dengan resolusi crop 9:16 matematis dari dimensi sumber masing-masing.
- Koreksi QA pada harness selesai dan status validasi Prioritas 3 dinyatakan **CLOSED (VALID)**.
