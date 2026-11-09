# SmartMop Flask Backend (Supabase)

## 1. Persiapan
1. Letakkan folder ini sebagai isi folder `smartmop/backend/` (atau salin file-file ke struktur backend yang sudah ada).
2. Buat virtual environment jika diperlukan:
   `python -m venv .venv`
3. Aktifkan:
   Windows CMD: `.venv\\Scripts\\activate`
   PowerShell: `.venv\\Scripts\\Activate.ps1`
4. Install:
   `pip install -r requirements.txt`
5. Salin `.env.example` menjadi `.env`, lalu isi DATABASE_URL Supabase.
6. Jangan commit `.env` ke GitHub.

## 2. Jalankan
Dari folder `backend`:
`python run.py`

API berjalan di `http://127.0.0.1:5000`.

## 3. Tes cepat
- GET `http://127.0.0.1:5000/api/health`
- GET `http://127.0.0.1:5000/api/devices`
- GET `http://127.0.0.1:5000/api/devices/status`
- GET `http://127.0.0.1:5000/api/dashboard`

## 4. Contoh POST heartbeat
POST `http://127.0.0.1:5000/api/device/heartbeat`
Content-Type: application/json

{
  "device_code": "ESP32_MAIN_01",
  "ip_address": "192.168.1.20",
  "wifi_rssi": -55,
  "firmware_version": "1.0.0"
}

## 5. Contoh POST telemetry
POST `http://127.0.0.1:5000/api/device/telemetry`
Content-Type: application/json

{
  "device_code": "ESP32_MAIN_01",
  "battery_voltage": 11.8,
  "battery_percent": 85.5,
  "wifi_rssi": -54
}

`soap_level_percent` hanya kirim jika perangkat memang memiliki sensor level sabun.

## 6. Contoh POST camera frame
POST `/api/camera/frame`
{
  "device_code": "ESP32_CAM_01",
  "image_path": "uploads/camera/frame_001.jpg",
  "has_spill": true,
  "highest_spill_confidence": 0.91,
  "model_name": "spill-yolo",
  "model_version": "1.0",
  "inference_ms": 42
}

## 7. Contoh POST detection
POST `/api/detections`
{
  "device_code": "ESP32_CAM_01",
  "class_name": "spill",
  "confidence": 0.91,
  "bbox_x": 0.20,
  "bbox_y": 0.25,
  "bbox_width": 0.30,
  "bbox_height": 0.22,
  "model_name": "spill-yolo",
  "model_version": "1.0",
  "inference_ms": 42,
  "decision_status": "accepted"
}

## Catatan penting
- Endpoint ini memakai nama tabel dan kolom dari schema.sql yang diberikan.
- Schema harus sudah dijalankan lengkap, termasuk app_settings, camera_frames, ALTER TABLE detections, dan view.
- Perangkat awal dari schema: SERVER_ML_01, ESP32_CAM_01, ESP32_MAIN_01.
- Endpoint ini belum menerapkan autentikasi API key/JWT. Jangan buka ke internet atau hubungkan perangkat produksi sebelum autentikasi dan HTTPS ditambahkan.
- Untuk deployment, gunakan WSGI server (misalnya Gunicorn) dan set DATABASE_URL sebagai environment variable di hosting.
- `image_path` hanya menyimpan lokasi file; endpoint upload gambar belum dibuat.
