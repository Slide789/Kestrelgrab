# Third-party software

Kestrelgrab's own source code is licensed under the MIT License (see `LICENSE`).
The repository contains no third-party code. The built application (`build.bat`,
installer) bundles the components below, each under its own license.

| Component | License | Source |
|---|---|---|
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | The Unlicense | https://github.com/yt-dlp/yt-dlp |
| [yt-dlp-ejs](https://github.com/yt-dlp/ejs) | The Unlicense | https://github.com/yt-dlp/ejs |
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | LGPL v3 | https://code.qt.io |
| [FFmpeg](https://ffmpeg.org) (binary from imageio-ffmpeg) | GPL v3 (build with libx264) | https://ffmpeg.org/download.html, https://github.com/imageio/imageio-binaries |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | BSD 2-Clause | https://github.com/imageio/imageio-ffmpeg |
| [Deno](https://deno.com) | MIT | https://github.com/denoland/deno |
| [Python](https://www.python.org) | PSF License | https://www.python.org |
| requests, urllib3, certifi, websockets, brotli, mutagen, pycryptodomex | Apache 2.0 / MIT / MPL 2.0 / BSD / GPL v2+ / BSD (see each package) | PyPI |

## Notes for redistributing the built app

- **FFmpeg (GPL):** If you distribute the built app or installer, you must include the
  GPL license text and offer the corresponding FFmpeg source code (a link to the exact
  source release is enough). Alternatively, distribute only the source code of this
  repository and let users run `build.bat` themselves.
- **Qt (LGPL):** PySide6 is dynamically linked; users may replace the Qt libraries in the
  `_internal\PySide6` folder of the built app.
- **mutagen (GPL v2+)** is an optional yt-dlp dependency used for embedding metadata.

Brand names (e.g. YouTube, TikTok, Instagram, X) belong to their owners. Kestrelgrab is
not affiliated with or endorsed by any of them.
