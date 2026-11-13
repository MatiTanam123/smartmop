# SMARTMOP Backend — Railway + Supabase + YOLO26

Folder ini adalah backend kanonis untuk repository SMARTMOP. Nama direktori harus **`backend`** (huruf kecil), sama dengan nama yang telah tercatat di Git.

## 1. Struktur

```text
backend/
├── app.py
├── config.py
├── run.py
├── requirements.txt
├── Procfile
├── .env.example
├── database/
│   ├── connection.py
│   ├── schema.sql
│   └── migrations/
│       ├── 001_app_settings.sql
│       ├── 002_camera_frames.sql
│       └── 003_soap_available.sql
├── ml/
│   ├── inference.py
│   ├── preprocess.py
│   └── models/
│       └── best.pt   # letakkan model hasil training di sini; tidak disertakan
├── routes/
├── services/
└── storage/captures/
```

## 2. Instalasi lokal Windows

Buka terminal pada folder `backend`:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Isi `.env` dengan `DATABASE_URL`, `DEVICE_API_KEY`, `ADMIN_API_KEY`, dan lokasi model. Jangan mengunggah `.env` ke GitHub.

Jalankan:

```powershell
python app.py
```

Health check:

- `http://127.0.0.1:5000/api/health`
- `http://127.0.0.1:5000/api/health/database`
- `http://127.0.0.1:5000/api/health/model`

`/api/health` dapat hidup ketika file bobot belum tersedia. Namun upload gambar akan mengembalikan HTTP 503 sampai `best.pt` dan runtime YOLO berhasil dimuat. Sistem tidak membuat hasil deteksi palsu.

## 3. Database Supabase

### Database baru

Jalankan **seluruh** `database/schema.sql` pada Supabase SQL Editor.

### Database lama yang sudah menjalankan schema sebelumnya

Jalankan migration berikut secara berurutan apabila belum pernah dijalankan:

1. `database/migrations/001_app_settings.sql`
2. `database/migrations/002_camera_frames.sql`
3. `database/migrations/003_soap_available.sql`

Migration 003 menambahkan `device_telemetry.soap_available BOOLEAN` untuk menampung data float switch yang sudah dikirim firmware controller. Jangan menjalankan ulang migration yang bersifat non-idempotent; file di atas memakai `IF NOT EXISTS` untuk penambahan kolom/tabel.

## 4. File bobot YOLO

Simpan file model hasil training pada:

```text
backend/ml/models/best.pt
```

Default konfigurasi:

```env
ML_MODEL_PATH=ml/models/best.pt
ML_MODEL_NAME=YOLO26
ML_MODEL_VERSION=custom-liquid-spill-v1
ML_IMAGE_SIZE=640
ML_CONFIDENCE=0.10
ML_DEVICE=cpu
```

`ML_CONFIDENCE` adalah confidence awal untuk mengambil kandidat YOLO. Keputusan diterima/ditolak akhir masih mengikuti `robot_settings.confidence_threshold` di database.

File `best.pt` tidak ada di ZIP sumber dan tidak disertakan di patch ini. Untuk deployment, pilih salah satu cara:

- Commit bobot ke **private Git repository** (jika ukuran file dan batas Git repository memungkinkan), atau
- Sediakan cara pengambilan model dari object storage private dan simpan ke volume Railway. Jangan membuat bucket model publik tanpa pertimbangan keamanan.

Jangan menganggap model berhasil dimuat hanya karena server Flask hidup. Verifikasi `/api/health/model` harus mengembalikan `model_available: true`.

## 5. API camera contract

ESP32-CAM mengirim satu frame sebagai multipart/form-data:

```http
POST /api/camera/upload
X-Device-Key: <DEVICE_API_KEY>
Content-Type: multipart/form-data
```

Field wajib:

- `image`: JPEG/PNG/WEBP
- `device_code`: `ESP32_CAM_01`

Field opsional:

- `captured_at`: timestamp ISO-8601, contoh `2026-11-13T10:00:00Z`

Contoh uji dari PowerShell:

```powershell
curl.exe -X POST "http://127.0.0.1:5000/api/camera/upload" `
  -H "X-Device-Key: ISI_DEVICE_API_KEY" `
  -F "device_code=ESP32_CAM_01" `
  -F "image=@C:\temp\foto_lantai.jpg;type=image/jpeg"
```

Backend menjalankan YOLO di server, menyimpan satu baris di `camera_frames` untuk setiap frame, dan menyimpan nol atau lebih hasil ke `detections`. Frame tanpa tumpahan tetap disimpan dengan `has_spill=false` dan tanpa baris deteksi jika YOLO tidak menemukan objek.

Website mengambil:

```http
GET /api/camera/latest-frame?device_code=ESP32_CAM_01
```

URL gambar dikembalikan sebagai `image_url`. Bounding box menggunakan koordinat ternormalisasi top-left `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height` (0 sampai 1), sesuai overlay frontend.

## 6. Kontrak ESP32 Main Controller

Semua endpoint perangkat menerima header `X-Device-Key` yang sama:

- `POST /api/device/heartbeat`
- `POST /api/device/telemetry`
- `GET /api/commands/pending?device_code=ESP32_MAIN_01`
- `POST /api/commands/<command_id>/ack`
- `PUT /api/cleaning/<session_id>/status`

Payload telemetri yang sudah didukung:

```json
{
  "device_code": "ESP32_MAIN_01",
  "battery_voltage": 11.8,
  "battery_percent": 85.5,
  "soap_available": true,
  "wifi_rssi": -54
}
```

`soap_available` adalah status boolean dari float switch, bukan persentase. `soap_level_percent` hanya diisi jika memang ada sensor level analog/kapasitif yang mengukur persentase.

## 7. Endpoint

| Method | Endpoint | Auth | Fungsi |
|---|---|---|---|
| GET | `/api/health` | Publik | Status aplikasi |
| GET | `/api/health/database` | Publik | Tes koneksi PostgreSQL |
| GET | `/api/health/model` | Publik | Tes kesiapan model |
| GET | `/api/dashboard` | Publik | Ringkasan dashboard |
| GET | `/api/devices` | Publik | Daftar perangkat |
| GET | `/api/devices/status` | Publik | Status koneksi perangkat |
| POST | `/api/device/heartbeat` | Device key | Heartbeat perangkat |
| POST | `/api/device/telemetry` | Device key | Telemetri perangkat |
| POST | `/api/camera/upload` | Device key | Upload + inferensi YOLO + simpan frame/detection |
| GET | `/api/camera/latest-frame` | Publik | Frame terbaru |
| GET | `/api/camera/frames/{id}/image` | Publik | File foto frame |
| GET | `/api/detections` | Publik | Riwayat hasil deteksi |
| GET | `/api/cleaning/history` | Publik | Riwayat pembersihan |
| GET | `/api/commands/pending` | Device key | Antrean command controller |
| POST | `/api/commands/{id}/ack` | Device key | ACK command |
| POST | `/api/commands` | Admin key | Membuat command |
| POST | `/api/cleaning/start` | Admin key | Membuat sesi pembersihan |
| PUT | `/api/cleaning/{id}/status` | Device key | Update status sesi dari controller |
| GET/PUT | `/api/settings` | GET publik, PUT admin key | Pengaturan robot |
| GET/PUT | `/api/notifications/settings` | GET publik, PUT admin key | Pengaturan notifikasi |
| GET/PUT | `/api/app-settings` | GET publik, PUT admin key | Pengaturan aplikasi |
| GET/POST | `/api/logs` | GET publik, POST admin key | Log aktivitas |

**Penting untuk frontend:** `ADMIN_API_KEY` tidak boleh ditulis di `api.js` atau file JavaScript browser. Dashboard yang sekarang belum mempunyai login administrator, sehingga aksi tulis dari browser (mode, settings, membuat command, mulai cleaning) akan ditolak HTTP 503/401 sampai kita menambahkan autentikasi pengguna yang aman. Pembacaan dashboard dan kamera tetap berjalan. Untuk pengujian endpoint admin sementara, gunakan Postman/curl dengan header `X-Admin-Key`, jangan masukkan secret itu ke frontend.

## 8. Automatic cleaning dan keselamatan robot

Service deteksi hanya menyimpan bukti AI, `has_spill`, confidence, dan status konfirmasi beberapa frame. **Service tidak langsung mengirim command motor atau `approach_spill` hanya berdasarkan gambar.** Firmware controller yang dikirim dalam repository melakukan gerakan maju untuk `approach_spill`; karena itu gerakan otomatis tidak diaktifkan oleh endpoint inferensi sebelum pemeriksaan keselamatan jarak/halangan, arah, dan emergency-stop diuji pada firmware.

## 9. Railway deployment

1. Commit folder `backend/` huruf kecil ke GitHub. Jangan commit `.env`, `__pycache__`, `.pio`, atau secret.
2. Buat service Railway dari repository.
3. Set **Root Directory** ke `/backend`.
4. Set **Start Command**:

```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 120
```

5. Set **Healthcheck Path** `/api/health`.
6. Tambahkan Railway Volume dan mount ke `/app/storage`; set `MEDIA_ROOT=/app/storage`.
7. Tambahkan environment variables dari daftar `.env.example`, dengan nilai produksi yang benar:
   - `APP_ENV=production`
   - `DATABASE_URL=...` (Supabase PostgreSQL connection string dengan SSL)
   - `FLASK_SECRET_KEY=...` (secret acak minimal 32 karakter)
   - `DEVICE_API_KEY=...` (secret acak yang sama dengan firmware)
   - `ADMIN_API_KEY=...` (gunakan sementara hanya dari Postman/curl; jangan expose ke browser)
   - `CORS_ORIGINS=https://domain-frontend-kamu`
   - `MEDIA_ROOT=/app/storage`
   - `ML_MODEL_PATH=ml/models/best.pt` (default, relatif terhadap folder backend).
8. Pastikan `best.pt` ada dan `/api/health/model` sukses.
9. Pastikan `/api/health/database` sukses.
10. Baru uji `POST /api/camera/upload` menggunakan foto uji.

Railway menjalankan proses melalui Start Command; jangan menjalankan Flask development server untuk production. Satu worker dipilih sebagai konfigurasi awal karena model YOLO akan dimuat di memori proses. Tambah worker hanya setelah pengukuran RAM/CPU.

## 10. Pemeriksaan akhir

Checklist sebelum firmware kamera dipakai:

- [ ] `GET /api/health` = 200
- [ ] `GET /api/health/database` = 200
- [ ] `GET /api/health/model` = 200 dan `model_available=true`
- [ ] Upload foto dengan Device Key benar = 201
- [ ] Foto muncul pada `camera_frames`
- [ ] Objek YOLO muncul pada `detections` jika ditemukan
- [ ] `GET /api/camera/latest-frame` mengembalikan `image_url`
- [ ] URL gambar dapat dibuka dari browser frontend
- [ ] Foto masih tersedia setelah Railway redeploy (Volume terpasang)

Belum ada tes terhadap database Supabase live atau file `best.pt` dalam paket ini. Tes tersebut wajib dilakukan di environment milik pengguna sebelum dinyatakan siap produksi.
