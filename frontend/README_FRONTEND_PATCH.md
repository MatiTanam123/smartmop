# Frontend patch yang diperlukan untuk backend Railway

Folder `frontend/` ini hanya berisi file pengganti. Salin file-file ini ke folder `frontend/` (huruf kecil) di repository.

File yang diganti:
- `assets/js/api.js`: mendukung URL backend HTTPS penuh dari Railway.
- `assets/js/app.js`: menghapus generator ilustrasi dummy; elemen lama menjadi placeholder netral.
- `assets/js/camera.js`: saat belum ada frame menampilkan status menunggu, bukan error palsu.
- `assets/js/dashboard.js`: thumbnail deteksi memakai `image_url` aktual dari endpoint.
- `assets/js/history.js`: gambar riwayat memakai foto aktual; bila kosong, menampilkan placeholder.
- `assets/css/components.css`: menghilangkan latar lantai ilustrasi dan menata foto/placeholder/bounding box.
- Backend `GET /api/detections` sekarang mengembalikan `image_url` untuk setiap deteksi yang terkait frame.
- `index.html`: memuat `camera.js` pada halaman beranda dan menyiapkan area kamera.

Di menu Pengaturan, isi alamat server dengan URL penuh backend Railway, contoh `https://NAMA-SERVICE.up.railway.app`. Untuk URL penuh, field port tidak digunakan. `apiPath` tetap `/api`.

Catatan: file ini tidak menambahkan login administrator. Endpoint yang mengubah mode, membuat command, atau memulai sesi tetap dilindungi `X-Admin-Key`. Jangan simpan `ADMIN_API_KEY` di JavaScript/browser. Buat alur login/session server-side sebelum mengaktifkan tombol kontrol pada website.
