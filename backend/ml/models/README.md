# YOLO model weights

Letakkan bobot model hasil training bernama `best.pt` pada folder ini:

```text
backend/ml/models/best.pt
```

File bobot tidak disertakan dalam ZIP perbaikan karena tidak tersedia dalam ZIP sumber. Tanpa bobot dan paket `ultralytics`, backend tetap dapat menjalankan health endpoint, tetapi `POST /api/camera/upload` mengembalikan HTTP 503 agar frame tidak disimpan dengan hasil AI palsu.

Untuk deployment Railway, pastikan file model tersedia pada filesystem container (misalnya melalui private Git repository atau proses download dari object storage private). Jangan simpan secret/storage token di source code.
