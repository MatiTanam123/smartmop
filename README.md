# SMARTMOP — Backend Flask + PostgreSQL

Paket ini menghubungkan frontend SmartMop yang ada di folder `frontend/` ke backend Python Flask dan database PostgreSQL. Backend menyediakan API untuk dashboard, riwayat deteksi, pengaturan, kontrol robot, heartbeat perangkat, antrean perintah ESP32, telemetri, dan upload gambar untuk inferensi ML.

> **Penting:** file bobot model terlatih `best.pt` tidak disertakan karena tidak ada pada ZIP sumber. Backend dan API dapat dijalankan tanpa bobot ML, tetapi inferensi otomatis baru aktif setelah tim meletakkan model YOLO terlatih di `backend/ml/models/best.pt`.

## 1. Arsitektur

```text
ESP32-CAM --HTTP upload image--> Flask API --> YOLO (best.pt)
                                      |             |
                                      v             v
                                  PostgreSQL <--- detections
                                      |
                         robot_commands (queue)
                                      |
                         ESP32 DevKit polling API
                                      |
                           motor roda / motor pel / pompa

Browser (frontend HTML/CSS/JS) <---- HTTP API ----> Flask
```

- **ESP32-CAM:** mengirim gambar ke `POST /api/camera/upload`.
- **Laptop/PC:** menjalankan Flask, PostgreSQL client, dan inferensi YOLO.
- **ESP32 DevKit:** mengirim heartbeat, mengambil antrean perintah, lalu mengirim acknowledgement/status.
- **PostgreSQL:** menyimpan data perangkat, deteksi, sesi pembersihan, perintah, log, pengaturan, dan telemetri.
- **Frontend:** disajikan Flask dari alamat root, sehingga frontend dan API memakai host/port yang sama.

Backend hanya memasukkan perintah ke antrean database. Gerakan fisik motor tetap harus diimplementasikan dan diuji pada firmware ESP32. Tambahkan juga tombol emergency-stop fisik yang memutus aktuator; endpoint software tidak menggantikan pemutus daya fisik.

## 2. Persyaratan

- Windows 10/11 (petunjuk disiapkan untuk Windows).
- Python 3.10 atau lebih baru; disarankan Python 3.11/3.12.
- PostgreSQL Server sudah terpasang dan service berjalan.
- Database `smartmop_db` sudah dibuat.
- pgAdmin 4 atau `psql` untuk menjalankan SQL.

## 3. Siapkan database

Di pgAdmin 4:

1. Buat database bernama `smartmop_db` (jika belum ada).
2. Klik database `smartmop_db` → Tools → Query Tool.
3. Buka dan jalankan seluruh isi file `backend/database/schema.sql` dengan F5.
4. File tersebut berisi sembilan tabel utama serta dua tabel pendukung backend: `app_settings` untuk parameter model/jaringan dan `camera_frames` untuk validasi frame kamera berturut-turut.

Tabel yang dibuat (sembilan tabel utama dari rancangan awal ditambah dua tabel pendukung backend):

- `devices`
- `device_heartbeats`
- `robot_settings`
- `notification_settings`
- `detections`
- `cleaning_sessions`
- `robot_commands`
- `activity_logs`
- `device_telemetry`
- `app_settings` (tambahan konfigurasi UI/network)
- `camera_frames` (mencatat setiap frame kamera, termasuk frame tanpa tumpahan)

View:

- `v_device_connection_status`

Jika sembilan tabel utama sudah pernah dibuat dari SQL sebelumnya, file `schema.sql` tetap bisa dijalankan. Migrasi `app_settings` dan `camera_frames` akan menambahkan tabel pendukung; kolom `detections.frame_id` juga ditambahkan jika belum ada.

## 4. Konfigurasi backend di Windows

1. Ekstrak ZIP ke folder, misalnya `C:\SmartMop_Backend_Project`.
2. Salin `.env.example` menjadi `.env`.
3. Buka `.env` lalu ubah `DATABASE_URL` sesuai password PostgreSQL kamu. Contoh:

```env
DATABASE_URL=postgresql://postgres:PasswordPostgresKamu@127.0.0.1:5432/smartmop_db
```

Jika password mengandung karakter khusus seperti `@`, `:`, `/`, `#` atau `%`, karakter tersebut perlu URL-encode pada connection string.

4. Jalankan `run_windows.bat`.
5. Script membuat virtual environment, memasang library, memeriksa tabel PostgreSQL, lalu menjalankan Flask.

Atau jalankan manual lewat CMD pada folder proyek:

```bat
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
python backend\database\check_db.py
python run.py
```

Setelah aktif, buka:

- Dashboard: http://127.0.0.1:5000/
- Health API: http://127.0.0.1:5000/api/health

Untuk membuka dashboard dari HP/laptop lain pada Wi-Fi yang sama, gunakan IP lokal komputer server, misalnya `http://192.168.1.10:5000/`. Izinkan Python pada Windows Firewall untuk jaringan Private.

## 5. Mengaktifkan YOLO

1. Letakkan bobot model hasil training tim di `backend/ml/models/best.pt`.
2. Install paket ML:

```bat
.venv\Scripts\activate
pip install -r backend\requirements-ml.txt
```

3. Restart backend.
4. Buka `http://127.0.0.1:5000/api/health`. Nilai `ml_available` harus `true`.

Setiap gambar yang berhasil diproses dicatat sebagai satu baris `camera_frames`, termasuk gambar yang tidak menghasilkan bounding box. Logika otomatis memeriksa frame berturut-turut dari tabel ini agar frame bersih terbaru membatalkan konfirmasi spill sebelumnya. Model diharapkan menghasilkan kelas yang dapat mengidentifikasi tumpahan, misalnya `syrup_spill`, `tumpahan_sirup`, atau `spill`. Kelas bersih sebaiknya menggunakan nama seperti `clean_floor` atau `no_spill`. Jika nama kelas model berbeda, sesuaikan fungsi `is_spill_class()` pada `backend/services/detection_service.py`.

Ketika model belum tersedia, endpoint upload tetap menerima gambar (jika penyimpanan gambar aktif), tetapi **tidak membuat hasil deteksi palsu**.

## 6. API utama

Semua endpoint API memiliki prefix `/api`.

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/health` | Cek server, PostgreSQL, dan status model ML |
| GET | `/dashboard` | Ringkasan robot, deteksi terbaru, log |
| GET | `/robot/status` | Status heartbeat controller dan telemetri |
| GET | `/history` | Riwayat deteksi dan status pembersihan |
| GET/POST | `/settings` | Baca/simpan pengaturan frontend |
| POST | `/robot/mode` | Ubah Otomatis/Manual dan antrekan perintah |
| POST | `/robot/move` | Antrekan perintah gerak manual |
| POST | `/robot/clean` | Mulai atau berhenti sesi pembersihan |
| POST | `/robot/pump` | Nyalakan/matikan pompa melalui antrean |
| POST | `/robot/motor` | Nyalakan/matikan motor pel melalui antrean |
| POST | `/robot/emergency-stop` | Antrekan perintah henti darurat |
| POST | `/camera/quality` | Antrekan pilihan kualitas kamera |
| POST | `/camera/upload` | Upload gambar ESP32-CAM dan jalankan YOLO |
| POST | `/detections` | Simpan output ML yang sudah dihitung oleh proses lain |
| POST | `/device/heartbeat` | Heartbeat ESP32/server |
| POST | `/device/telemetry` | Simpan baterai, level sabun, RSSI (bila sensor tersedia) |
| GET | `/device/commands` | Ambil antrean perintah untuk perangkat |
| POST | `/device/commands/<id>/ack` | Acknowledge hasil eksekusi perintah |
| POST | `/device/sessions/<id>/status` | Laporkan status sesi pengepelan |
| GET | `/captures/<filename>` | Ambil gambar yang disimpan backend |

### Contoh heartbeat ESP32 DevKit

```http
POST /api/device/heartbeat
Content-Type: application/json

{
  "device_code": "ESP32_MAIN_01",
  "wifi_rssi": -58,
  "firmware_version": "0.1.0"
}
```

### Contoh upload gambar ESP32-CAM

Kirim `multipart/form-data` dengan field file bernama `image` dan field teks `device_code` bernilai `ESP32_CAM_01` ke:

```text
POST http://IP_SERVER:5000/api/camera/upload
```

### Contoh polling command oleh ESP32 DevKit

```http
GET /api/device/commands?device_code=ESP32_MAIN_01&limit=5
```

Contoh respons:

```json
{
  "ok": true,
  "commands": [
    {
      "command_id": 12,
      "session_id": 4,
      "command_type": "clean_start",
      "payload": {"action": "start"}
    }
  ]
}
```

Setelah perintah diproses firmware, kirim:

```http
POST /api/device/commands/12/ack
Content-Type: application/json

{"status":"acknowledged","response":{"message":"accepted by controller"}}
```

Status sesi dilaporkan melalui `/api/device/sessions/4/status`, misalnya:

```json
{
  "status": "completed",
  "verification_result": "clean",
  "verification_confidence": 0.94,
  "mop_duration_seconds": 12,
  "notes": "Area terlihat bersih pada foto verifikasi"
}
```

## 7. Keamanan dan keselamatan

- Jangan membuka port server Flask ke internet publik tanpa autentikasi dan HTTPS.
- Untuk menambahkan autentikasi perangkat, isi `DEVICE_API_KEY` pada `.env`. ESP32 harus mengirim header `X-Device-Key` pada endpoint device (`heartbeat`, `telemetry`, polling command, ack, dan upload kamera).
- Jangan menyimpan password Wi-Fi dalam frontend atau database sebagai teks biasa. Field SSID pada pengaturan hanya menyimpan nama jaringan.
- Pasang emergency-stop hardware yang memutus suplai ke driver motor/pompa. Perintah API hanya jalur software.
- Firmware harus memastikan motor dan pompa OFF ketika Wi-Fi/server hilang atau command tidak lagi valid.
- Jangan mengirim persentase baterai/sabun contoh. Telemetri hanya ditampilkan sebagai nilai aktual bila perangkat memang mengukur nilainya.

## 8. Catatan integrasi frontend

Folder `frontend/` dari ZIP sumber dipertahankan dan backend menyajikannya pada root. Beberapa penyesuaian integrasi kecil disertakan:

- Dashboard dapat menampilkan `--` jika data baterai/sabun belum tersedia.
- ID elemen baterai dan atribut timestamp pada `index.html` diperbaiki.
- `settings.js` mencoba memuat pengaturan dari PostgreSQL dan mengirim perubahan ke endpoint `/api/settings`.

Jika menjalankan frontend dengan Live Server terpisah, isi IP server dan port `5000` pada pengaturan jaringan, atau buka frontend langsung dari `http://IP_SERVER:5000/`.

## 9. Troubleshooting

**`connection refused` / PostgreSQL tidak terhubung**
- Pastikan service PostgreSQL Running pada `services.msc`.
- Periksa password, port (default 5432), dan nama database pada `.env`.
- Jalankan `python backend/database/check_db.py`.

**Tabel `app_settings` tidak ditemukan**
- Jalankan ulang seluruh `backend/database/schema.sql` pada database `smartmop_db`.

**`ml_available: false`**
- Pastikan `best.pt` benar-benar ada dan bukan file kosong.
- Install `backend/requirements-ml.txt` dan restart backend.

**ESP32 tidak menerima command**
- Pastikan heartbeat menggunakan `device_code` yang sama dengan data seed: `ESP32_MAIN_01`.
- Pastikan controller dan laptop berada pada Wi-Fi/LAN yang sama.
- Periksa `GET /api/device/commands?device_code=ESP32_MAIN_01`.
- Pastikan firmware melakukan polling secara berkala dan mengirim ack.

**Frontend menampilkan data contoh**
- Buka `/api/health` dahulu. Pastikan database connected.
- Pastikan dashboard dibuka melalui alamat backend atau `serverIP` mengarah ke IP server yang benar.

---

Backend ini adalah fondasi integrasi prototipe. Logika gerak fisik, kalibrasi pompa, mapping koordinat deteksi ke pergerakan, serta verifikasi kebersihan harus divalidasi pada perangkat dan firmware robot yang sebenarnya.
