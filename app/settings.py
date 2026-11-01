"""Persistente Einstellungen über QSettings (Windows-Registry)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from . import APP_NAME, i18n
from .core import AUDIO_FORMATS, COOKIE_BROWSERS, VIDEO_FORMATS


def default_download_dir() -> str:
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    if not path:
        path = str(Path.home() / "Downloads")
    return str(Path(path) / APP_NAME)


class Settings:
    def __init__(self, qsettings: QSettings | None = None) -> None:
        self._s = qsettings or QSettings(APP_NAME, APP_NAME)

    def _get(self, key: str, default):
        value = self._s.value(key, default)
        return default if value is None else value

    # Sprache
    @property
    def language(self) -> str:
        lang = str(self._get("language", ""))
        return lang if lang in i18n.LANGUAGES else i18n.DEFAULT_LANGUAGE

    @language.setter
    def language(self, value: str) -> None:
        self._s.setValue("language", value)

    # Download-Ordner
    @property
    def download_dir(self) -> str:
        return str(self._get("download_dir", "") or default_download_dir())

    @download_dir.setter
    def download_dir(self, value: str) -> None:
        self._s.setValue("download_dir", value)

    # Parallele Downloads (1–5)
    @property
    def parallel(self) -> int:
        try:
            n = int(self._get("parallel", 2))
        except (TypeError, ValueError):
            n = 2
        return max(1, min(5, n))

    @parallel.setter
    def parallel(self, value: int) -> None:
        self._s.setValue("parallel", max(1, min(5, int(value))))

    # Cookies aus Browser ("" = keine)
    @property
    def cookies_browser(self) -> str:
        value = str(self._get("cookies_browser", ""))
        return value if value in COOKIE_BROWSERS else ""

    @cookies_browser.setter
    def cookies_browser(self, value: str) -> None:
        self._s.setValue("cookies_browser", value or "")

    # Zuletzt gewählte Formate
    @property
    def video_format(self) -> str:
        value = str(self._get("video_format", "mp4"))
        return value if value in VIDEO_FORMATS else "mp4"

    @video_format.setter
    def video_format(self, value: str) -> None:
        self._s.setValue("video_format", value)

    @property
    def audio_format(self) -> str:
        value = str(self._get("audio_format", "mp3"))
        return value if value in AUDIO_FORMATS else "mp3"

    @audio_format.setter
    def audio_format(self, value: str) -> None:
        self._s.setValue("audio_format", value)

    # Fenstergeometrie
    def geometry(self):
        return self._s.value("geometry")

    def set_geometry(self, data) -> None:
        self._s.setValue("geometry", data)

    def sync(self) -> None:
        self._s.sync()
