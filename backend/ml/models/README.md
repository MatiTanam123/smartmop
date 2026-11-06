# Model Machine Learning

Folder ini disediakan untuk bobot model YOLO hasil training tim.

1. Letakkan file bobot bernama `best.pt` di folder ini, atau ubah `ML_MODEL_PATH` pada `.env`.
2. Install paket tambahan dengan `pip install -r backend/requirements-ml.txt`.
3. Restart backend.
4. Periksa `GET /api/health`; nilai `ml_available` harus `true`.

File bobot model tidak disertakan karena model terlatih milik proyek belum tersedia di file sumber yang diberikan.
