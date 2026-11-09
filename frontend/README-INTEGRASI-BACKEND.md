# SmartMop Frontend - versi terintegrasi dengan backend Flask

Frontend ini mempertahankan desain, halaman, gambar, dan CSS dari frontend awal, tetapi JavaScript API diselaraskan dengan route pada backend ZIP yang diberikan.

## Menjalankan

1. Ekstrak folder `frontend` dari ZIP ini.
2. Jalankan backend dari folder `backend`:
   ```bash
   python run.py
   ```
3. Pastikan tes backend berhasil:
   `http://127.0.0.1:5000/api/health`
4. Buka `frontend/index.html` melalui Live Server / server web lokal (disarankan), bukan dengan mengubah file API.
5. Pada Pengaturan > Jaringan:
   - Server IP: kosongkan jika browser dan Flask berjalan pada komputer yang sama.
   - Port API: `5000`
   - Endpoint API: `/api`
   - IP ESP32-CAM dan Controller: isi setelah mengetahui IP perangkat.
6. Klik Simpan Pengaturan, lalu refresh halaman.

Jika website dibuka dari perangkat lain, isi Server IP dengan IP LAN komputer yang menjalankan Flask, misalnya `192.168.1.x`. Pastikan firewall Windows mengizinkan port 5000 dan komputer serta perangkat berada pada jaringan yang sama.

## Endpoint backend yang digunakan

| Fitur frontend | Endpoint backend |
|---|---|
| Tes backend | `GET /api/health` |
| Dashboard | `GET /api/dashboard` |
| Status perangkat | `GET /api/devices/status` |
| Deteksi | `GET /api/detections?limit=...` |
| Log | `GET /api/logs?limit=...` |
| Riwayat pembersihan | `GET /api/cleaning/history` |
| Mulai sesi | `POST /api/cleaning/start` |
| Perbarui status sesi | `PUT /api/cleaning/<id>/status` |
| Buat perintah robot | `POST /api/commands` |
| Pengaturan robot | `GET/PUT /api/settings` |
| Pengaturan aplikasi | `GET/PUT /api/app-settings` |
| Notifikasi | `GET/PUT /api/notifications/settings` |

## Perintah yang dimasukkan ke antrean robot

Frontend membuat record `robot_commands` untuk:
- `move` dengan payload `{ "direction": "up|down|left|right|stop" }`
- `clean_start`
- `clean_stop`
- `pump_set` dengan payload `{ "on": true|false }`
- `mop_motor_set` dengan payload `{ "on": true|false }`
- `emergency_stop`
- `camera_quality` (ditujukan ke `ESP32_CAM_01`)

Firmware ESP32 harus melakukan polling `GET /api/commands/pending?device_code=ESP32_MAIN_01` (kamera menggunakan `ESP32_CAM_01`), menjalankan command, lalu mengirim acknowledgement ke `POST /api/commands/<command_id>/ack`.

**Penting:** endpoint backend saat ini belum menyediakan autentikasi API. Jangan membuka backend ke internet. Emergency stop dari website hanya mengantrekan perintah; robot tetap harus mempunyai tombol/pemutus daya fisik.

## Batasan yang memang berasal dari backend saat ini

- Backend belum menyediakan upload file gambar. `image_path` hanya metadata lokasi file.
- Live Camera mencoba stream langsung `http://IP_ESP32_CAM:81/stream`; stream ini bukan video yang diproksikan melalui Flask.
- Status perangkat dianggap online jika heartbeat diterima dalam 60 detik.
- Level sabun hanya akan tampil jika perangkat benar-benar mengirim `soap_level_percent`. Tanpa sensor level sabun, tampil `--`, bukan angka simulasi.
- Frontend tidak lagi mengganti kegagalan API dengan data mock secara diam-diam. Jika backend gagal, halaman menampilkan pesan error supaya data contoh tidak disangka data Supabase.
