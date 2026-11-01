"""Download-Logik ohne Qt-Abhängigkeit (dadurch direkt testbar).

Enthält: Suche nach ffmpeg und JS-Runtime, URL-Erkennung, Analyse (fetch_info),
Berechnung der verfügbaren Qualitätsstufen, Aufbau der yt-dlp-Optionen,
Download mit Fortschritts-Callback und Abbruch sowie Fehlerklassifizierung.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yt_dlp
from yt_dlp.utils import DownloadCancelled

# --------------------------------------------------------------------------- #
# Konstanten
# --------------------------------------------------------------------------- #

QUALITY_TIERS: tuple[int, ...] = (2160, 1440, 1080, 720, 480, 360)
QUALITY_BEST = "best"
QUALITY_AUDIO = "audio"

VIDEO_FORMATS: tuple[str, ...] = ("mp4", "mkv", "webm")
AUDIO_FORMATS: tuple[str, ...] = ("mp3", "m4a", "opus", "flac", "wav")

COOKIE_BROWSERS: tuple[str, ...] = ("chrome", "firefox", "edge", "brave", "opera", "vivaldi")

OUTTMPL = "%(title).150B [%(id)s].%(ext)s"
OUTTMPL_AUDIO = "%(title).150B [%(id)s] (audio).%(ext)s"

PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"

# Fehlercodes (werden in der UI übersetzt)
ERR_LOGIN = "login"
ERR_UNSUPPORTED = "unsupported"
ERR_UNAVAILABLE = "unavailable"
ERR_NETWORK = "network"
ERR_FFMPEG = "ffmpeg"
ERR_CANCELLED = "cancelled"
ERR_UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Pfade und externe Werkzeuge
# --------------------------------------------------------------------------- #

def is_frozen() -> bool:
    """True, wenn die App als PyInstaller-Paket läuft."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Ordner der ausführbaren Datei (gepackt) bzw. das Projektverzeichnis."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Ordner mit den gebündelten Daten (assets/, tools/)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return app_dir()


def _tool_dirs() -> list[Path]:
    dirs = [app_dir() / "tools", resource_dir() / "tools"]
    unique: list[Path] = []
    for d in dirs:
        if d not in unique:
            unique.append(d)
    return unique


def _find_tool(exe_name: str) -> str | None:
    for d in _tool_dirs():
        candidate = d / exe_name
        if candidate.is_file():
            return str(candidate)
    return shutil.which(exe_name)


def find_ffmpeg() -> str | None:
    """tools/ffmpeg.exe → PATH → imageio-ffmpeg."""
    path = _find_tool("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return None


def find_js_runtime() -> tuple[str, str] | None:
    """Liefert (name, pfad) der JS-Runtime: tools/deno.exe → deno im PATH → node im PATH."""
    suffix = ".exe" if os.name == "nt" else ""
    deno = _find_tool("deno" + suffix)
    if deno:
        return "deno", deno
    node = shutil.which("node" + suffix)
    if node:
        return "node", node
    return None


def ytdlp_version() -> str:
    return yt_dlp.version.__version__


# --------------------------------------------------------------------------- #
# URL-Erkennung
# --------------------------------------------------------------------------- #

_URL_RE = re.compile(
    r"""(?ix)
    (?:https?://)?                              # optionales Schema
    (?:www\.)?
    (?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+ # Domain-Teile
    [a-z]{2,24}                                 # TLD
    (?::\d{2,5})?                               # Port
    (?:/[^\s<>"'`]*)?                           # Pfad
    """
)
_LOCAL_URL_RE = re.compile(r"(?i)https?://(?:localhost|\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?(?:/[^\s<>\"'`]*)?")


def normalize_url(text: str) -> str:
    """Entfernt Leerzeichen/Satzzeichen am Ende und ergänzt fehlendes https://."""
    url = text.strip().strip("<>\"'")
    url = url.rstrip(".,;:!?)]}")
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"(?i)^[a-z][a-z0-9+.-]*://", url):
        url = "https://" + url
    return url


def extract_urls(text: str) -> list[str]:
    """Findet alle Links im Text (auch ohne Schema) – ohne Duplikate, in Reihenfolge."""
    if not text:
        return []
    found: list[tuple[int, str]] = []
    taken: list[tuple[int, int]] = []
    for m in _LOCAL_URL_RE.finditer(text):
        found.append((m.start(), m.group(0)))
        taken.append(m.span())
    for m in _URL_RE.finditer(text):
        start, end = m.span()
        if any(s <= start < e for s, e in taken):
            continue
        # E-Mail-Adressen ignorieren
        if start > 0 and text[start - 1] == "@":
            continue
        candidate = m.group(0)
        if "." not in candidate.split("/")[0 if "://" not in candidate else 2]:
            continue
        found.append((start, candidate))
    found.sort(key=lambda x: x[0])
    result: list[str] = []
    for _, raw in found:
        url = normalize_url(raw)
        if url and url not in result:
            result.append(url)
    return result


# --------------------------------------------------------------------------- #
# Fehlerklassifizierung
# --------------------------------------------------------------------------- #

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

_ERROR_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (ERR_FFMPEG, (
        "ffmpeg", "ffprobe", "postprocessing", "merging of", "conversion failed",
        "audio conversion failed",
    )),
    (ERR_UNSUPPORTED, (
        "unsupported url", "is not a valid url", "no suitable extractor",
        "unsupported site",
    )),
    (ERR_LOGIN, (
        "sign in", "log in", "login", "logged-in", "cookies", "private video",
        "this video is private", "confirm your age", "age-restricted", "age restricted",
        "members-only", "members only", "authentication", "account", "not a bot",
        "http error 401", "requires payment", "premium",
    )),
    (ERR_UNAVAILABLE, (
        "video unavailable", "unavailable", "not available", "has been removed",
        "was removed", "does not exist", "doesn't exist", "no longer available",
        "http error 404", "http error 410", "not found", "no video formats",
        "no video could be found", "requested format is not available",
        "geo restricted", "blocked it in your country", "ip address is blocked", "copyright",
        "there is no video in this post",
    )),
    (ERR_NETWORK, (
        "unable to download webpage", "unable to download", "urlopen error", "timed out",
        "timeout", "connection", "getaddrinfo", "name or service not known",
        "temporary failure", "nodename nor servname", "network is unreachable",
        "ssl", "certificate", "http error 5", "remote end closed", "winerror 100",
        "max retries", "unable to connect", "failed to resolve", "proxy",
        "http error 429", "too many requests",
    )),
]


def clean_error_message(msg: str) -> str:
    """Entfernt ANSI-Farben, 'ERROR:'-Präfixe und Hinweis-Floskeln von yt-dlp."""
    msg = _ANSI_RE.sub("", str(msg or "")).strip()
    msg = re.sub(r"^(?:ERROR:\s*)+", "", msg)
    msg = re.sub(r"^\[[^\]]+\]\s*", "", msg)
    msg = msg.split("; please report this issue")[0]
    msg = msg.split(" Use --cookies")[0]
    msg = msg.split("; Use --cookies")[0]
    msg = msg.strip()
    if len(msg) > 300:
        msg = msg[:297] + "…"
    return msg


def classify_error(error: BaseException | str) -> str:
    """Ordnet einen Fehler (Exception oder Text) einer Fehlerkategorie zu."""
    if isinstance(error, (DownloadCancelled, CancelledByUser)):
        return ERR_CANCELLED
    text = _ANSI_RE.sub("", str(error)).lower()
    for code, needles in _ERROR_PATTERNS:
        if any(n in text for n in needles):
            return code
    return ERR_UNKNOWN


class CancelledByUser(DownloadCancelled):
    """Wird im Progress-Hook ausgelöst, um einen Download abzubrechen."""

    msg = "Download cancelled by user"


class KestrelgrabError(Exception):
    """Fehler mit Kategorie (code) und bereinigtem Detailtext."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def to_kestrelgrab_error(exc: BaseException) -> KestrelgrabError:
    if isinstance(exc, KestrelgrabError):
        return exc
    return KestrelgrabError(classify_error(exc), clean_error_message(str(exc)))


# --------------------------------------------------------------------------- #
# yt-dlp-Basis
# --------------------------------------------------------------------------- #

class _QuietLogger:
    """Fängt die Ausgaben von yt-dlp ab, damit nichts auf der Konsole landet."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def debug(self, msg: str) -> None:  # noqa: D401 – yt-dlp-Schnittstelle
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)


def base_options(cookies_browser: str | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "windowsfilenames": True,
        "continuedl": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 20,
        "logger": _QuietLogger(),
    }
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    runtime = find_js_runtime()
    if runtime:
        name, path = runtime
        opts["js_runtimes"] = {name: {"path": path}}
    if cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    return opts


# --------------------------------------------------------------------------- #
# Analyse
# --------------------------------------------------------------------------- #

@dataclass
class MediaInfo:
    url: str
    id: str = ""
    title: str = ""
    uploader: str = ""
    duration: float | None = None
    thumbnail: str | None = None
    extractor: str = ""
    qualities: list[str | int] = field(default_factory=lambda: [QUALITY_BEST, QUALITY_AUDIO])
    portrait: bool = False

    @property
    def duration_text(self) -> str:
        return format_duration(self.duration)


def format_duration(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return ""
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _short_side(fmt: dict[str, Any]) -> int | None:
    h = fmt.get("height")
    w = fmt.get("width")
    if isinstance(h, int) and isinstance(w, int) and h > 0 and w > 0:
        return min(h, w)
    if isinstance(h, int) and h > 0:
        return h
    return None


def is_portrait(formats: list[dict[str, Any]]) -> bool:
    best = None
    for f in formats or []:
        w, h = f.get("width"), f.get("height")
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            if best is None or w * h > best[0] * best[1]:
                best = (w, h)
    return bool(best and best[1] > best[0])


def compute_qualities(formats: list[dict[str, Any]] | None) -> list[str | int]:
    """Ermittelt die tatsächlich verfügbaren Qualitätsstufen.

    Eine Stufe H wird nur angeboten, wenn es ein Videoformat gibt, dessen kurze
    Seite in (nächstniedrigere Stufe, H] liegt – sonst würde die Auswahl dasselbe
    Ergebnis wie eine niedrigere Stufe liefern. Höhere Auflösungen als 2160p
    zählen zur Stufe 2160.
    """
    formats = formats or []
    sides: set[int] = set()
    has_audio = False
    for f in formats:
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")
        if acodec not in (None, "none") or (vcodec in (None,) and acodec is None):
            has_audio = True
        if vcodec == "none":
            continue
        side = _short_side(f)
        if side:
            sides.add(side)

    result: list[str | int] = [QUALITY_BEST]
    tiers = sorted(QUALITY_TIERS)  # aufsteigend
    for i, tier in enumerate(tiers):
        lower = tiers[i - 1] if i > 0 else 0
        upper_unbounded = tier == tiers[-1]
        if any(lower < s <= tier or (upper_unbounded and s > tier) for s in sides):
            result.append(tier)
    # Absteigend sortiert: best, 2160, ..., 360
    ints = sorted((q for q in result if isinstance(q, int)), reverse=True)
    result = [QUALITY_BEST, *ints]
    # Formate ohne jede Codec-Information (z. B. direkte Links) enthalten meist Audio.
    if has_audio or not formats:
        result.append(QUALITY_AUDIO)
    return result


def _pick_thumbnail(info: dict[str, Any]) -> str | None:
    thumbs = info.get("thumbnails") or []
    # Qt kann JPEG/PNG sicher darstellen; WebP nur mit Plugin → JPEG bevorzugen.
    for t in reversed(thumbs):
        url = t.get("url") or ""
        if url and not re.search(r"\.webp(?:$|\?)", url, re.I):
            return url
    return info.get("thumbnail") or (thumbs[-1].get("url") if thumbs else None)


def fetch_info(url: str, cookies_browser: str | None = None,
               extra_opts: dict[str, Any] | None = None) -> MediaInfo:
    """Analysiert eine URL (ohne Download). Wirft KestrelgrabError."""
    url = normalize_url(url)
    opts = base_options(cookies_browser)
    opts["skip_download"] = True
    opts["playlist_items"] = "1"
    if extra_opts:
        opts.update(extra_opts)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp wirft DownloadError, ExtractorError, …
        raise to_kestrelgrab_error(exc) from None
    if not info:
        raise KestrelgrabError(ERR_UNAVAILABLE, "")

    if info.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise KestrelgrabError(ERR_UNAVAILABLE, "Playlist is empty")
        info = entries[0]

    formats = info.get("formats") or ([info] if info.get("url") else [])
    return MediaInfo(
        url=info.get("webpage_url") or info.get("original_url") or url,
        id=str(info.get("id") or ""),
        title=info.get("title") or info.get("id") or url,
        uploader=info.get("uploader") or info.get("channel") or info.get("uploader_id") or "",
        duration=info.get("duration"),
        thumbnail=_pick_thumbnail(info),
        extractor=info.get("extractor_key") or info.get("extractor") or "",
        qualities=compute_qualities(formats),
        portrait=is_portrait(formats),
    )


def fetch_bytes(url: str, timeout: float = 10.0, limit: int = 8 * 1024 * 1024) -> bytes | None:
    """Lädt kleine Dateien (Thumbnails). Gibt bei Fehlern None zurück."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Kestrelgrab"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(limit)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

@dataclass
class DownloadRequest:
    url: str
    folder: str
    quality: str | int = QUALITY_BEST   # "best", "audio" oder Höhe in Pixeln
    fmt: str = "mp4"                     # Container bzw. Audioformat
    cookies_browser: str | None = None
    portrait: bool = False

    @property
    def is_audio(self) -> bool:
        return self.quality == QUALITY_AUDIO


def build_format(quality: str | int, portrait: bool = False, has_ffmpeg: bool = True) -> str:
    dim = "width" if portrait else "height"
    if quality == QUALITY_AUDIO:
        return "ba/b"
    if isinstance(quality, int):
        if has_ffmpeg:
            return f"bv*[{dim}<={quality}]+ba/b[{dim}<={quality}]/b"
        return f"b[{dim}<={quality}]/b"
    return "bv*+ba/b" if has_ffmpeg else "b"


def build_download_options(req: DownloadRequest, ffmpeg: str | None) -> dict[str, Any]:
    """Erzeugt die yt-dlp-Optionen für einen Job (ohne Hooks)."""
    opts = base_options(req.cookies_browser)
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    else:
        opts.pop("ffmpeg_location", None)
    has_ffmpeg = ffmpeg is not None

    template = OUTTMPL_AUDIO if req.is_audio else OUTTMPL
    opts["paths"] = {"home": req.folder}
    opts["outtmpl"] = {"default": template}
    opts["format"] = build_format(req.quality, req.portrait, has_ffmpeg)
    postprocessors: list[dict[str, Any]] = []

    if req.is_audio:
        if has_ffmpeg:
            codec = req.fmt if req.fmt in AUDIO_FORMATS else "mp3"
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": "0" if codec == "mp3" else "",
            })
        opts["format_sort"] = ["acodec:m4a"] if req.fmt == "m4a" else []
    elif has_ffmpeg:
        fmt = req.fmt if req.fmt in VIDEO_FORMATS else "mp4"
        if fmt == "mp4":
            opts["format_sort"] = ["res", "vcodec:h264", "acodec:m4a"]
            opts["merge_output_format"] = "mp4"
            postprocessors.append({"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"})
        elif fmt == "mkv":
            opts["merge_output_format"] = "mkv"
            postprocessors.append({"key": "FFmpegVideoRemuxer", "preferedformat": "mkv"})
        else:  # webm
            opts["format_sort"] = ["res", "vcodec:vp9", "acodec:opus"]
            opts["merge_output_format"] = "webm/mkv"
            # Wandelt nur um, wenn das Ergebnis noch kein WEBM ist.
            postprocessors.append({"key": "FFmpegVideoConvertor", "preferedformat": "webm"})
    if postprocessors:
        opts["postprocessors"] = postprocessors
    return opts


ProgressCallback = Callable[[dict[str, Any]], None]


class _ProgressTracker:
    """Rechnet die Teil-Downloads (Video + Audio) in einen Gesamtfortschritt um."""

    def __init__(self, cb: ProgressCallback | None, cancel: threading.Event | None):
        self.cb = cb
        self.cancel = cancel
        self.done_parts = 0
        self.seen_files: set[str] = set()
        self.title_sent = False

    def _check_cancel(self) -> None:
        if self.cancel is not None and self.cancel.is_set():
            raise CancelledByUser()

    def _emit(self, data: dict[str, Any]) -> None:
        if self.cb:
            self.cb(data)

    def progress_hook(self, d: dict[str, Any]) -> None:
        self._check_cancel()
        info = d.get("info_dict") or {}
        parts = max(1, len(info.get("requested_formats") or []) or 1)
        status = d.get("status")
        base: dict[str, Any] = {}
        if not self.title_sent and info.get("title"):
            base["title"] = info.get("title")
            self.title_sent = True
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            frac = (done / total) if total else None
            overall = None
            if frac is not None:
                overall = min(1.0, (self.done_parts + min(frac, 1.0)) / parts)
            self._emit({**base, "status": "downloading", "progress": overall,
                        "speed": d.get("speed"), "eta": d.get("eta"),
                        "downloaded": done, "total": total})
        elif status == "finished":
            fn = d.get("filename") or ""
            if fn not in self.seen_files:
                self.seen_files.add(fn)
                self.done_parts += 1
            self._emit({**base, "status": "downloading",
                        "progress": min(1.0, self.done_parts / parts),
                        "speed": None, "eta": None})

    def postprocessor_hook(self, d: dict[str, Any]) -> None:
        self._check_cancel()
        if d.get("status") == "started":
            self._emit({"status": "processing", "progress": 1.0,
                        "postprocessor": d.get("postprocessor")})


def _final_path(info: dict[str, Any]) -> str | None:
    for item in info.get("requested_downloads") or []:
        p = item.get("filepath") or item.get("_filename")
        if p:
            return p
    return info.get("filepath") or info.get("_filename")


def run_download(req: DownloadRequest,
                 progress_cb: ProgressCallback | None = None,
                 cancel_event: threading.Event | None = None,
                 extra_opts: dict[str, Any] | None = None) -> str:
    """Lädt herunter und liefert den Pfad der fertigen Datei.

    Wirft KestrelgrabError (code=cancelled bei Abbruch).
    """
    os.makedirs(req.folder, exist_ok=True)
    ffmpeg = find_ffmpeg()
    opts = build_download_options(req, ffmpeg)
    tracker = _ProgressTracker(progress_cb, cancel_event)
    opts["progress_hooks"] = [tracker.progress_hook]
    opts["postprocessor_hooks"] = [tracker.postprocessor_hook]
    if extra_opts:
        opts.update(extra_opts)
    logger: _QuietLogger = opts["logger"]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(normalize_url(req.url), download=True)
    except BaseException as exc:
        if cancel_event is not None and cancel_event.is_set():
            raise KestrelgrabError(ERR_CANCELLED, "") from None
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        err = to_kestrelgrab_error(exc)
        if err.code == ERR_UNKNOWN and logger.errors:
            err = KestrelgrabError(classify_error(logger.errors[-1]),
                                 clean_error_message(logger.errors[-1]))
        raise err from None
    if cancel_event is not None and cancel_event.is_set():
        raise KestrelgrabError(ERR_CANCELLED, "")
    if info and info.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in (info.get("entries") or []) if e]
        info = entries[0] if entries else {}
    path = _final_path(info or {})
    if not path or not os.path.exists(path):
        detail = clean_error_message(logger.errors[-1]) if logger.errors else "File not found"
        raise KestrelgrabError(classify_error(detail) if logger.errors else ERR_UNKNOWN, detail)
    return path


# --------------------------------------------------------------------------- #
# Update-Check
# --------------------------------------------------------------------------- #

def parse_version(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", v or ""))


def latest_ytdlp_version(timeout: float = 10.0) -> str:
    req = urllib.request.Request(PYPI_URL, headers={"User-Agent": "Kestrelgrab"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return str(data["info"]["version"])


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def pip_update_ytdlp() -> tuple[bool, str]:
    """Aktualisiert yt-dlp per pip (nur Dev-Modus). Liefert (ok, ausgabe)."""
    if is_frozen():
        return False, "frozen"
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default,curl-cffi]"],
        capture_output=True, text=True, creationflags=flags,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, out[-2000:]
