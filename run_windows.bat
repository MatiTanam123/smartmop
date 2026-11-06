@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo          SMARTMOP - BACKEND LOCAL
echo ================================================

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Membuat virtual environment...
    py -3 -m venv .venv
    if errorlevel 1 goto error
) else (
    echo [1/4] Virtual environment sudah tersedia.
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [INFO] File .env dibuat. Edit DATABASE_URL dan password PostgreSQL.
)

echo [2/4] Memasang dependensi backend...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 goto error

echo [3/4] Memeriksa koneksi PostgreSQL...
.venv\Scripts\python.exe backend\database\check_db.py
if errorlevel 1 goto error

echo [4/4] Menjalankan SmartMop...
.venv\Scripts\python.exe run.py
goto end

:error
echo.
echo Terjadi kesalahan. Periksa pesan di atas dan baca README.md.
pause
:end
endlocal
