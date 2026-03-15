@echo off
setlocal EnableDelayedExpansion
title Izellik Chatbot - Baslatiliyor...

echo.
echo  ================================================
echo    Izellik Makeup House - WhatsApp Chatbot
echo  ================================================
echo.

:: Proje dizinine git
cd /d "%~dp0"

:: ─── 1. .env kontrolu ────────────────────────────────────
if not exist ".env" (
    echo  [HATA] .env dosyasi bulunamadi!
    echo.
    echo         Lutfen proje klasorundeki .env.example dosyasini
    echo         kopyalayip .env olarak kaydedin ve API anahtarlarini girin.
    echo.
    pause
    exit /b 1
)
echo  [OK]  .env dosyasi bulundu

:: ─── 2. Python kontrolu ──────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [HATA] Python bulunamadi!
    echo.
    echo         Lutfen Python 3.10 veya ustunu yukleyin:
    echo         https://www.python.org/downloads/
    echo.
    echo         Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin!
    echo.
    pause
    exit /b 1
)

:: Python surumunu al ve kontrol et
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)
if !PYMAJ! LSS 3 (
    echo  [HATA] Python 3.10+ gerekli, bulunan: !PYVER!
    pause
    exit /b 1
)
if !PYMAJ! EQU 3 if !PYMIN! LSS 10 (
    echo  [HATA] Python 3.10+ gerekli, bulunan: !PYVER!
    pause
    exit /b 1
)
echo  [OK]  Python !PYVER! bulundu

:: ─── 3. Sanal ortam (venv) ───────────────────────────────
if not exist ".venv\Scripts\activate.bat" (
    echo  [INFO] Sanal ortam olusturuluyor...
    python -m venv .venv
    if errorlevel 1 (
        echo  [HATA] Sanal ortam olusturulamadi!
        pause
        exit /b 1
    )
    echo  [OK]  Sanal ortam olusturuldu: .venv
) else (
    echo  [OK]  Sanal ortam mevcut: .venv
)

:: Sanal ortami aktifle
call .venv\Scripts\activate.bat
echo  [OK]  Sanal ortam aktiflestirildi

:: ─── 4. pip guncelle ─────────────────────────────────────
echo  [INFO] pip guncelleniyor...
python -m pip install --upgrade pip -q --disable-pip-version-check
echo  [OK]  pip guncellendi

:: ─── 5. Python kutuphanelerini kur ───────────────────────
echo  [INFO] Python kutuphaneleri kuruluyor...
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo  [HATA] Kutuphaneler yuklenemedi! requirements.txt kontrol edin.
    pause
    exit /b 1
)
echo  [OK]  Python kutuphaneleri hazir

:: ─── 6. Admin UI build (Node.js varsa) ───────────────────
if not exist "admin-ui\dist\index.html" (
    node --version >nul 2>&1
    if not errorlevel 1 (
        echo  [INFO] Admin UI derleniyor...
        cd admin-ui
        call npm install -q 2>nul
        call npm run build 2>nul
        cd ..
        if exist "admin-ui\dist\index.html" (
            echo  [OK]  Admin UI derlendi
        ) else (
            echo  [UYARI] Admin UI derlenemedi, devam ediliyor...
        )
    ) else (
        echo  [UYARI] Node.js bulunamadi - Admin UI devre disi
        echo          Node.js icin: https://nodejs.org/
    )
) else (
    echo  [OK]  Admin UI mevcut
)

:: ─── 7. Sunucuyu baslat ──────────────────────────────────
echo.
echo  ================================================
echo   Sunucu baslatiliyor...
echo   Adres : http://localhost:8000
echo   Admin : http://localhost:8000/admin-ui
echo   Docs  : http://localhost:8000/docs
echo   Dur   : CTRL+C
echo  ================================================
echo.
title Izellik Chatbot - Calisiyor ^| http://localhost:8000

uvicorn main:app --host 0.0.0.0 --port 8000 --reload

echo.
echo  [INFO] Sunucu durduruldu.
pause
