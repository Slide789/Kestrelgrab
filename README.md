# Kestrelgrab

Desktop-App für Windows zum Speichern von Videos und Audio von allen Seiten, die
[yt-dlp](https://github.com/yt-dlp/yt-dlp) unterstützt. Oberfläche auf Deutsch und Englisch, modernes Dark-Theme.

## Funktionen

- Link einfügen per Button **Einfügen**, Enter-Taste oder Drag and Drop.
  Enthält der Text mehrere Links, landen alle direkt in der Warteschlange.
  Fehlendes `https://` wird ergänzt.
- Analyse mit Vorschaubild, Titel, Kanal und Dauer. Im Qualitätsmenü stehen nur Stufen,
  die es für das Video wirklich gibt (Beste, 2160p–360p, Nur Audio).
- Formate: Video als MP4, MKV oder WEBM, Audio als MP3, M4A, OPUS, FLAC oder WAV.
- Warteschlange mit Fortschritt, Geschwindigkeit und Restzeit, 1–5 parallele Downloads,
  Abbrechen, Wiederholen (Teil-Downloads werden fortgesetzt), Datei öffnen, Im Ordner zeigen.
- Einstellungen: Sprache, Download-Ordner, Parallelität, Cookies aus dem Browser
  (Chrome, Firefox, Edge, Brave, Opera, Vivaldi), yt-dlp-Version mit Update-Prüfung,
  Status von ffmpeg und JS-Runtime.
- Verständliche, übersetzte Fehlermeldungen (Anmeldung nötig, nicht unterstützt,
  nicht verfügbar, Netzwerk, ffmpeg).
- Audio-Dateien bekommen den Zusatz „ (audio)“ im Namen und überschreiben so kein
  gleichnamiges Video.

## Start im Dev-Modus

Voraussetzung: Python 3.12 (64 Bit).

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python tools\make_icon.py
.venv\Scripts\python main.py
```

**ffmpeg** wird in dieser Reihenfolge gesucht: `tools\ffmpeg.exe`, `PATH`, dann das
mitgelieferte Binary von `imageio-ffmpeg`. Fehlt ffmpeg, zeigt die App ein Warnbanner
und lädt Einzeldateien ohne Zusammenführen oder Umwandlung.

**JS-Runtime (für YouTube):** yt-dlp braucht für YouTube eine JavaScript-Runtime.
Gesucht wird `tools\deno.exe`, dann `deno` im `PATH`, dann `node` im `PATH`.

### Tests

```bat
.venv\Scripts\python -m pytest
```

Die Core-Tests erzeugen per ffmpeg ein Testvideo, stellen es über einen lokalen
`http.server` bereit und laden es über den Generic-Extractor von yt-dlp herunter
(Video, MKV, MP3, Abbruch und Fortsetzen, Fehlerfälle). Der UI-Smoketest läuft mit
`QT_QPA_PLATFORM=offscreen` und braucht kein sichtbares Fenster.

## Build

```bat
build.bat
```

Das Skript legt das venv an, installiert die Abhängigkeiten, erzeugt das Icon, kopiert
`ffmpeg.exe` (aus imageio-ffmpeg) und lädt `deno.exe` aus den offiziellen
Deno-GitHub-Releases nach `tools\`. Danach baut PyInstaller (`--onedir`) die App nach
`dist\Kestrelgrab\Kestrelgrab.exe`.

## Installer

1. [Inno Setup 6](https://jrsoftware.org/isinfo.php) installieren.
2. Nach `build.bat` die Datei `installer.iss` in Inno Setup öffnen und kompilieren, oder:

   ```bat
   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer.iss
   ```

Der Installer (Deutsch/Englisch) landet in `installer\Kestrelgrab-Setup-1.0.0.exe` und legt
einen Startmenü-Eintrag, auf Wunsch ein Desktop-Icon und einen Deinstallationseintrag an.

## yt-dlp aktuell halten

Die Seiten ändern sich oft, deshalb erscheinen regelmäßig neue yt-dlp-Versionen.
Wenn Downloads plötzlich scheitern, ist ein Update meist die Lösung.

- **Dev-Modus:** In den Einstellungen „Nach Updates suchen“ und dann „Jetzt aktualisieren“
  wählen (führt `pip install -U "yt-dlp[default]"` aus), anschließend die App neu starten.
- **Gepackte App:** Die App zeigt nur einen Hinweis auf die neue Version. Für das Update
  `build.bat` erneut ausführen (installiert die neueste yt-dlp-Version) und den Installer
  neu bauen.

## Rechtlicher Hinweis

Lade nur Inhalte herunter, an denen du die Rechte hast oder deren Nutzung erlaubt ist.
Beachte die Nutzungsbedingungen der jeweiligen Plattform und das Urheberrecht.
Kestrelgrab ist ein Werkzeug; für die Nutzung ist allein der Anwender verantwortlich.

## Lizenz

Der Quellcode von Kestrelgrab steht unter der [MIT-Lizenz](LICENSE). Die gebaute App
enthält Fremdsoftware mit eigenen Lizenzen (u. a. FFmpeg unter GPL), siehe
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Kestrelgrab steht in keiner Verbindung
zu den Plattformen, von denen Inhalte geladen werden.

## Projektstruktur

```
main.py                 Einstiegspunkt (AppUserModelID, Icon)
app/core.py             Download-Logik ohne Qt (testbar)
app/workers.py          QThreads für Analyse, Downloads, Update-Check
app/i18n.py             Deutsch/Englisch mit Live-Umschaltung
app/settings.py         Einstellungen (QSettings)
app/ui/                 Hauptfenster, Karten, Einstellungsdialog, Stylesheet
assets/                 App-Icon (von tools/make_icon.py erzeugt)
tools/                  make_icon.py sowie ffmpeg.exe/deno.exe (vom Build)
tests/                  Core-Tests und UI-Smoketest
```
