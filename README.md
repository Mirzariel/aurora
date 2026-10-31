# AURORA

Situs showcase capstone A-06, DTETI 2026: rancangan pemantauan lampu jalan tenaga surya melalui sensor, LoRa, dan dashboard. HTML, CSS, JavaScript, dan font lokal; tanpa proses build atau pustaka aplikasi tambahan.

## Pratinjau lokal

Jalankan server statis dari folder ini, misalnya:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Buka `http://127.0.0.1:8765/`. Parameter `?static` menonaktifkan adegan sticky. Tanpa JavaScript, seluruh konten dan kelima tahap perjalanan tetap tersedia. Mode pengurangan gerak, hemat data, layar sempit, atau layar yang tidak cukup tinggi memakai layout linear.

## Arah desain

Lihat [docs/DESIGN.md](docs/DESIGN.md). Cerita bergerak dari suasana pembuka, konteks PJU-TS, perjalanan informasi, hardware, dashboard, bukti, lalu tim. Hanya satu bagian memakai adegan sticky dengan scroll normal sebagai pengendali. Foto dan video stok diberi konteks yang jelas.

## Asal aset

- [docs/ASSET-PROVENANCE.md](docs/ASSET-PROVENANCE.md): aset Claude yang dipertahankan dan tambahan baru.
- [docs/GENERATED-ASSETS.md](docs/GENERATED-ASSETS.md): ilustrasi hero, prompt, dan sumber generatif.
- [docs/STOCK-MEDIA.md](docs/STOCK-MEDIA.md): sumber, kredit, lisensi foto dan video stok.
- [docs/3D-ASSET-REVIEW.md](docs/3D-ASSET-REVIEW.md): asal model PCB lama, izin visualisasi, DRC, dan keterbatasan render.
- [assets/img/CREDITS.md](assets/img/CREDITS.md): kredit gambar.

Video aurora/LoRa sebelumnya, generator, logo, dan render lama tetap tersimpan pada jalur asal. Video lama belum dikoreksi seluruh keterangannya dan tidak digunakan sebagai bukti atau animasi utama halaman. Viewer 3D yang belum selesai tidak dimuat.

## Batas klaim

Hero adalah ilustrasi generatif. Foto PJU-TS dan video stok bukan rekaman uji AURORA. Render PCB berasal dari model lama dan tidak membuktikan kesiapan fabrikasi maupun kecocokan dengan revisi papan saat ini. Dashboard memakai data simulasi. Hasil bench, emulasi, cloud test, target, dan hal yang belum diuji tetap dibedakan.

## Pemeriksaan

```powershell
node --check assets/js/main.js
```

Hasil pemeriksaan browser tersedia dalam [docs/VALIDATION.md](docs/VALIDATION.md). Perubahan disiapkan untuk peninjauan lokal; commit, push, dan publikasi dilakukan terpisah sesuai instruksi pengguna.
