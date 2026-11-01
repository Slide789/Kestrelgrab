@echo off
REM ==========================================================================
REM  Kestrelgrab – Build-Skript
REM  Legt ein venv an, installiert Abhaengigkeiten, erzeugt das Icon,
REM  legt ffmpeg.exe und deno.exe nach tools\ und baut mit PyInstaller.
REM  Ergebnis: dist\Kestrelgrab\Kestrelgrab.exe
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=py -3.12"
%PY% --version >nul 2>&1 || set "PY=python"

if not exist ".venv\Scripts\python.exe" (
    echo [1/6] Erstelle virtuelle Umgebung ...
    %PY% -m venv .venv || goto :error
) else (
    echo [1/6] Virtuelle Umgebung vorhanden.
)
set "VPY=.venv\Scripts\python.exe"

echo [2/6] Installiere Abhaengigkeiten ...
"%VPY%" -m pip install --upgrade pip >nul || goto :error
"%VPY%" -m pip install --upgrade -r requirements.txt || goto :error

echo [3/6] Erzeuge Icon ...
"%VPY%" tools\make_icon.py || goto :error

echo [4/6] Kopiere ffmpeg nach tools\ ...
"%VPY%" -c "import imageio_ffmpeg, shutil; shutil.copyfile(imageio_ffmpeg.get_ffmpeg_exe(), r'tools\ffmpeg.exe')" || goto :error

echo [5/6] Lade Deno (JS-Runtime fuer YouTube) ...
if exist "tools\deno.exe" (
    echo        tools\deno.exe vorhanden - uebersprungen.
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol='Tls12';" ^
      "$zip=Join-Path $env:TEMP 'deno-kestrelgrab.zip';" ^
      "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' -OutFile $zip;" ^
      "Expand-Archive -Force -Path $zip -DestinationPath 'tools';" ^
      "Remove-Item $zip" || (
        echo        WARNUNG: Deno konnte nicht geladen werden. YouTube-Downloads brauchen dann Node/Deno im PATH.
    )
)

echo [6/6] Baue mit PyInstaller ...
"%VPY%" -m PyInstaller --noconfirm --clean ^
    --windowed --onedir --name Kestrelgrab --icon assets/icon.ico ^
    --add-data "assets;assets" --add-data "tools;tools" ^
    --add-data "LICENSE;." --add-data "THIRD_PARTY_NOTICES.md;." ^
    --collect-all yt_dlp --collect-all yt_dlp_ejs --collect-all imageio_ffmpeg ^
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtPdf --exclude-module PySide6.QtMultimedia ^
    --exclude-module tkinter --exclude-module pytest ^
    main.py || goto :error

echo.
echo Fertig: dist\Kestrelgrab\Kestrelgrab.exe
echo Installer: Inno Setup oeffnen und installer.iss kompilieren
echo            ^(oder: "%%ProgramFiles(x86)%%\Inno Setup 6\ISCC.exe" installer.iss^)
exit /b 0

:error
echo.
echo FEHLER: Der Build ist fehlgeschlagen (siehe Ausgabe oben).
exit /b 1
