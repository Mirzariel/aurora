# AURORA

Situs showcase proyek capstone AURORA (A-06, DTETI 2026): monitoring lampu jalan tenaga surya (PJU-TS) dengan komunikasi LoRa.

Situs statis: HTML, CSS, dan JS biasa. Tanpa build, tanpa pustaka luar. Buka `index.html` lewat server lokal apa pun, misalnya:

```bash
python -m http.server 8765
```

lalu buka `http://127.0.0.1:8765/`. Tambahkan `?static` pada alamat untuk menampilkan semua bagian tanpa animasi scroll-reveal.

## Memasang video YouTube

Di `index.html`, cari `data-youtube-id=""` pada bagian `#video`, lalu isi dengan 11 karakter ID video (bagian setelah `v=` pada tautan). Video baru dimuat dari `youtube-nocookie.com` setelah tombol putar ditekan.

## Isi folder

- `assets/video/`: loop aurora hero dan ilustrasi alur paket LoRa (mp4 dan webm). Skrip pembuatnya ada di `assets/tools/`.
- `assets/img/`: foto, render PCB, dan tangkapan layar dashboard (data simulasi). Kredit foto ada di `assets/img/CREDITS.md`.
- `assets/fonts/`: Geist dan Geist Mono, lisensi SIL OFL 1.1.

## Catatan kejujuran

Situs ini memuat label bukti (BENCH_RF, EMULASI, HOST_TEST, CLOUD_TEST, NOT RUN) dan daftar hal yang belum terbukti. Render PCB adalah visualisasi desain, bukan foto perangkat. Data demo bertanda `simulated`.

## Kredit

Foto Unsplash dipakai di bawah Unsplash License (fotografer tercantum di footer situs). Font Geist © The Geist Project Authors, SIL OFL 1.1.
