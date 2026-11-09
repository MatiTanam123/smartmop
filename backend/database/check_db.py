
import os
import psycopg
from dotenv import load_dotenv

# Membaca file .env di folder yang sama
load_dotenv()

# Mengambil URL database
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL tidak ditemukan!")
    exit()

try:
    connection = psycopg.connect(DATABASE_URL)

    print("BERHASIL TERHUBUNG KE SUPABASE!")

    connection.close()

except Exception as e:
    print("Gagal terhubung ke database:")
    print(e)
