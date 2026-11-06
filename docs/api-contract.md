# SmartMop API Contract — Ringkasan untuk firmware

Base URL contoh: `http://192.168.1.10:5000/api`

## Heartbeat
`POST /device/heartbeat`
```json
{"device_code":"ESP32_MAIN_01","wifi_rssi":-55,"firmware_version":"0.1.0"}
```

Device code yang sudah disiapkan oleh schema:
- `SERVER_ML_01`
- `ESP32_CAM_01`
- `ESP32_MAIN_01`

## Upload kamera
`POST /camera/upload` sebagai multipart/form-data:
- `image`: file JPEG/PNG/WEBP
- `device_code`: `ESP32_CAM_01`

Backend menjalankan model jika `best.pt` telah dipasang.

## Poll command
`GET /device/commands?device_code=ESP32_MAIN_01&limit=5`

Jenis command yang saat ini dapat diantrikan:
- `set_mode`: `{ "mode": "automatic" | "manual" }`
- `move`: `{ "direction": "maju|mundur|kiri|kanan|berhenti" }`
- `clean_start`, `clean_stop`
- `pump_set`: `{ "on": true|false }`
- `mop_motor_set`: `{ "on": true|false }`
- `emergency_stop`: `{ "stop_all": true }`
- `camera_quality`: `{ "quality": "HD"|"SD" }`
- `approach_spill`: informasi confidence, kelas, dan bounding box ternormalisasi.

## Ack command
`POST /device/commands/{command_id}/ack`
```json
{"status":"acknowledged","response":{"ok":true}}
```
`status` hanya `acknowledged` atau `failed`.

## Update status sesi
`POST /device/sessions/{session_id}/status`
```json
{
  "status":"completed",
  "verification_result":"clean",
  "verification_confidence":0.92,
  "mop_duration_seconds":10
}
```
Status yang diterima: `approaching`, `mopping`, `verifying`, `completed`, `failed`, `cancelled`.

## Telemetri (opsional)
`POST /device/telemetry`
```json
{
  "device_code":"ESP32_MAIN_01",
  "battery_voltage":11.7,
  "battery_percent":82,
  "wifi_rssi":-55
}
```
Kirim `soap_level_percent` hanya bila ada sensor level sabun yang terpasang. Jangan mengirim nilai estimasi sebagai pengukuran sensor.

Jika `.env` memiliki `DEVICE_API_KEY`, setiap permintaan device wajib menyertakan header `X-Device-Key`.

## Frame kamera dan konfirmasi otomatis

Setiap panggilan `/camera/upload` yang berhasil diproses menambahkan satu baris `camera_frames`, termasuk bila `detections` kosong (`has_spill=false`). Sistem baru memasukkan command `approach_spill` bila sejumlah `confirmation_frames` terakhir semuanya memiliki `has_spill=true` dan semua confidence memenuhi threshold AI. Ini membantu menghindari trigger berdasarkan deteksi lama setelah kamera melihat lantai bersih.
