@echo off
setlocal
chcp 65001 >nul
title TubeFlow
cd /d "%~dp0"

echo.
echo  TubeFlow baslatiliyor...
echo.

powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1" -ProjectDir "%~dp0."
if errorlevel 1 echo [UYARI] Masaustu kisayolu olusturulamadi; uygulama baslatilmaya devam edilecek.

where py >nul 2>nul
if errorlevel 1 (
    echo [HATA] Python Launcher bulunamadi. Python 3.10 veya uzeri kurup tekrar deneyin.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

py -3.10 --version >nul 2>nul
if errorlevel 1 (
    py -3 --version >nul 2>nul
    if errorlevel 1 (
        echo [HATA] Python 3 bulunamadi. Python 3.10 veya uzeri kurup tekrar deneyin.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Sanal ortam olusturuluyor...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo [HATA] Sanal ortam olusturulamadi.
        pause
        exit /b 1
    )
)

echo [2/3] Gerekli Python paketleri kontrol ediliyor...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [HATA] Paketler kurulamadi. Internet baglantinizi kontrol edin.
    pause
    exit /b 1
)

echo [3/4] FFmpeg kontrol ediliyor...
".venv\Scripts\python.exe" install_ffmpeg.py
if errorlevel 1 (
    echo [UYARI] FFmpeg otomatik kurulamadi. LoreFlow yine acilacak; MP3 donusumu kullanilamayabilir.
)

echo [4/4] LoreFlow aciliyor. Kapatmak icin Ctrl+C basin.
".venv\Scripts\python.exe" run.py
if errorlevel 1 (
    echo [HATA] TubeFlow baslatilamadi. Yukaridaki mesaji kontrol edin.
    pause
)
endlocal
