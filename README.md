# Kestrelgrab

Kestrelgrab is a Windows desktop app for saving video and audio from sites supported by
[yt-dlp](https://github.com/yt-dlp/yt-dlp). The interface uses a dark theme and is
available in English and German.

## Features

- Add links with the Paste button, the Enter key, or drag and drop. Text with several
  links adds all of them to the queue at once, and links without `https://` are
  completed automatically.
- Each link is analyzed first, showing its thumbnail, title, channel and duration. The
  quality menu offers only the resolutions the source provides, from 2160p down to
  360p, plus "best" and "audio only".
- Video is saved as MP4, MKV or WEBM. Audio is saved as MP3, M4A, OPUS, FLAC or WAV.
- The download queue shows progress, speed and remaining time, and runs between one
  and five downloads in parallel. Downloads can be cancelled and retried, and a retry
  resumes the partial file. Finished files open directly or in Explorer.
- Settings cover the language, the download folder, the number of parallel downloads
  and an optional browser for cookies (Chrome, Firefox, Edge, Brave, Opera or Vivaldi).
  The settings also show the installed yt-dlp version, check for updates, and report
  whether ffmpeg and a JavaScript runtime are available.
- Errors appear as short messages in the selected language. The app distinguishes
  between content that requires a sign-in, unsupported sites, unavailable content,
  network problems and ffmpeg failures.
- Audio files carry the suffix " (audio)" in their name, so they never overwrite a
  video with the same title.

## Running from source

Kestrelgrab requires Python 3.12 (64-bit).

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python tools\make_icon.py
.venv\Scripts\python main.py
```

The app searches for ffmpeg in `tools\ffmpeg.exe`, then on `PATH`, and finally falls
back to the binary bundled with `imageio-ffmpeg`. If none is found, a warning appears
and downloads are saved as single files without merging or conversion.

YouTube requires a JavaScript runtime. The app uses `tools\deno.exe` if present,
otherwise `deno` or `node` from `PATH`.

Some sites, TikTok among them, reject requests that do not come from a real browser.
yt-dlp handles this through `curl_cffi`, which `requirements.txt` installs.

### Tests

```bat
.venv\Scripts\python -m pytest
```

The core tests generate a short video with ffmpeg, serve it from a local `http.server`
and download it through yt-dlp's generic extractor. They cover video, MKV and MP3
downloads, cancelling and resuming, and error handling. The UI smoke test runs with
`QT_QPA_PLATFORM=offscreen` and does not open a window.

## Building

```bat
build.bat
```

The build script sets up the virtual environment, installs the dependencies and
generates the icon. It then copies `ffmpeg.exe` from imageio-ffmpeg into `tools\` and
downloads `deno.exe` from the official Deno releases on GitHub. Finally, PyInstaller
(`--onedir`) builds the app into `dist\Kestrelgrab\Kestrelgrab.exe`.

## Installer

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php).
2. After running `build.bat`, open `installer.iss` in Inno Setup and compile it, or run:

   ```bat
   "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer.iss
   ```

The result is `installer\Kestrelgrab-Setup-1.0.0.exe`. The installer supports English
and German and creates a Start menu entry, an optional desktop shortcut and an
uninstaller.

## Updating yt-dlp

Video sites change frequently, and yt-dlp publishes updates to follow those changes.
When downloads start failing, updating yt-dlp is usually the fix.

When running from source, open the settings and use "Check for updates", then
"Update now". This runs `pip install -U "yt-dlp[default,curl-cffi]"`; restart the app afterwards.

The built app only reports that a new version is available. To update it, run
`build.bat` again, which installs the latest yt-dlp, and rebuild the installer.

## Legal notice

Only download content that you own or are permitted to use. Respect the terms of
service of each platform and the copyright law that applies to you. Users are solely
responsible for the content they download with Kestrelgrab.

## License

Kestrelgrab is released under the [MIT License](LICENSE). The built app bundles
third-party software under its own licenses, including FFmpeg under the GPL; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Kestrelgrab is not affiliated with
any of the platforms it downloads from.

## Project layout

```
main.py                 Entry point (AppUserModelID, icon)
app/core.py             Download logic without Qt, so it can be tested directly
app/workers.py          QThreads for analysis, downloads and the update check
app/i18n.py             English and German strings, switchable at runtime
app/settings.py         Settings (QSettings)
app/ui/                 Main window, cards, settings dialog, stylesheet
assets/                 App icon (generated by tools/make_icon.py)
tools/                  make_icon.py, plus ffmpeg.exe and deno.exe after a build
tests/                  Core tests and the UI smoke test
```
