@echo off
setlocal EnableDelayedExpansion
title Izellik Chatbot - Durdur

echo.
echo  ================================================
echo    Izellik Makeup House - Sunucu Durdur
echo  ================================================
echo.

set FOUND=0

:: PID dosyasindan bul
if exist "%~dp0.chatbot.pid" (
    set /p PID=<"%~dp0.chatbot.pid"
    if defined PID (
        tasklist /FI "PID eq !PID!" 2>nul | find "!PID!" >nul
        if not errorlevel 1 (
            echo  [INFO] Surec durduruluyor (PID: !PID!)...
            taskkill /PID !PID! /F >nul 2>&1
            del /f "%~dp0.chatbot.pid" >nul 2>&1
            echo  [OK]  Sunucu durduruldu.
            set FOUND=1
        ) else (
            del /f "%~dp0.chatbot.pid" >nul 2>&1
        )
    )
)

:: PID dosyasi yoksa port 8000'den bul
if "!FOUND!"=="0" (
    echo  [INFO] Port 8000 aranıyor...
    for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
        if not "%%a"=="0" (
            set PID=%%a
            set FOUND=1
        )
    )

    if "!FOUND!"=="1" (
        echo  [INFO] Surec bulundu (PID: !PID!), durduruluyor...
        taskkill /PID !PID! /F >nul 2>&1
        echo  [OK]  Sunucu durduruldu.
    ) else (
        echo  [INFO] Calisan sunucu bulunamadi.
    )
)

echo.
pause
