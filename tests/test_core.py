"""Tests für app/core.py mit lokalem HTTP-Server (yt-dlp Generic-Extractor)."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import pytest

from app import core

# --------------------------------------------------------------------------- #
# Hilfen
# --------------------------------------------------------------------------- #


def probe(path: str) -> dict:
    """Liest Streams per ffmpeg aus (ffprobe ist bei imageio-ffmpeg nicht dabei)."""
    ffmpeg = core.find_ffmpeg()
    proc = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True)
    out = proc.stderr
    return {"video": "Video:" in out, "audio": "Audio:" in out, "raw": out}


# --------------------------------------------------------------------------- #
# URL-Erkennung
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text, expected", [
    ("https://www.youtube.com/watch?v=abc", ["https://www.youtube.com/watch?v=abc"]),
    ("youtube.com/watch?v=abc", ["https://youtube.com/watch?v=abc"]),
    ("www.tiktok.com/@user/video/123", ["https://www.tiktok.com/@user/video/123"]),
    ("  http://x.com/user/status/1  ", ["http://x.com/user/status/1"]),
    ("Schau mal: https://youtu.be/xyz.", ["https://youtu.be/xyz"]),
    ("(https://instagram.com/p/AbC/)", ["https://instagram.com/p/AbC/"]),
    ("http://127.0.0.1:8000/a.mp4", ["http://127.0.0.1:8000/a.mp4"]),
    ("kein link hier", []),
    ("", []),
])
def test_extract_urls_single(text, expected):
    assert core.extract_urls(text) == expected


def test_extract_urls_multiple_and_dedupe():
    text = """https://youtu.be/a
    tiktok.com/@u/video/1  https://youtu.be/a
    https://x.com/u/status/2, mail@example.com"""
    assert core.extract_urls(text) == [
        "https://youtu.be/a",
        "https://tiktok.com/@u/video/1",
        "https://x.com/u/status/2",
    ]


def test_normalize_url():
    assert core.normalize_url("youtube.com/x") == "https://youtube.com/x"
    assert core.normalize_url("//cdn.example.com/v.mp4") == "https://cdn.example.com/v.mp4"
    assert core.normalize_url(" https://a.de/b, ") == "https://a.de/b"


# --------------------------------------------------------------------------- #
# Qualitätsstufen
# --------------------------------------------------------------------------- #


def _fmt(h, w=None, vcodec="avc1", acodec="none"):
    return {"height": h, "width": w or int(h * 16 / 9), "vcodec": vcodec, "acodec": acodec}


def test_qualities_from_real_formats():
    formats = [
        {"vcodec": "none", "acodec": "opus"},
        _fmt(144), _fmt(360), _fmt(720), _fmt(1080),
    ]
    assert core.compute_qualities(formats) == ["best", 1080, 720, 360, "audio"]


def test_qualities_gap_not_offered():
    # 1080 und 360 vorhanden → 720/480 würden 360p liefern und werden nicht angeboten
    formats = [_fmt(1080, acodec="aac"), _fmt(360, acodec="aac")]
    assert core.compute_qualities(formats) == ["best", 1080, 360, "audio"]


def test_qualities_odd_heights_and_8k():
    formats = [_fmt(4320), _fmt(1012), _fmt(240), {"vcodec": "none", "acodec": "mp4a"}]
    # 4320 zählt zu 2160, 1012 liegt in (720, 1080], 240 liegt unter 360
    assert core.compute_qualities(formats) == ["best", 2160, 1080, 360, "audio"]


def test_qualities_portrait_uses_short_side():
    formats = [_fmt(1920, 1080, acodec="aac"), _fmt(1280, 720, acodec="aac")]
    assert core.compute_qualities(formats) == ["best", 1080, 720, "audio"]
    assert core.is_portrait(formats) is True


def test_qualities_video_only_without_audio():
    assert core.compute_qualities([_fmt(720)]) == ["best", 720]


def test_qualities_unknown_formats():
    assert core.compute_qualities([{"url": "x"}]) == ["best", "audio"]
    assert core.compute_qualities([]) == ["best", "audio"]


# --------------------------------------------------------------------------- #
# Optionen
# --------------------------------------------------------------------------- #


def test_build_options_mp4(tmp_path):
    req = core.DownloadRequest("https://a.b/c", str(tmp_path), 720, "mp4")
    opts = core.build_download_options(req, "ffmpeg.exe")
    assert opts["format"] == "bv*[height<=720]+ba/b[height<=720]/b"
    assert opts["format_sort"] == ["res", "vcodec:h264", "acodec:m4a"]
    assert opts["merge_output_format"] == "mp4"
    assert opts["outtmpl"]["default"] == "%(title).150B [%(id)s].%(ext)s"
    assert opts["windowsfilenames"] is True and opts["noplaylist"] is True
    assert opts["ffmpeg_location"] == "ffmpeg.exe"


def test_build_options_audio_suffix(tmp_path):
    req = core.DownloadRequest("https://a.b/c", str(tmp_path), "audio", "flac")
    opts = core.build_download_options(req, "ffmpeg.exe")
    assert opts["outtmpl"]["default"].endswith(" (audio).%(ext)s")
    assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    assert opts["postprocessors"][0]["preferredcodec"] == "flac"


def test_build_options_without_ffmpeg(tmp_path):
    req = core.DownloadRequest("https://a.b/c", str(tmp_path), 1080, "mp4")
    opts = core.build_download_options(req, None)
    assert opts["format"] == "b[height<=1080]/b"
    assert "merge_output_format" not in opts and "postprocessors" not in opts
    assert "ffmpeg_location" not in opts


def test_build_options_portrait(tmp_path):
    req = core.DownloadRequest("https://a.b/c", str(tmp_path), 720, "mkv", portrait=True)
    opts = core.build_download_options(req, "ffmpeg.exe")
    assert opts["format"] == "bv*[width<=720]+ba/b[width<=720]/b"
    assert opts["merge_output_format"] == "mkv"


def test_cookies_and_js_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "find_js_runtime", lambda: ("deno", r"C:\tools\deno.exe"))
    opts = core.base_options("firefox")
    assert opts["cookiesfrombrowser"] == ("firefox",)
    assert opts["js_runtimes"] == {"deno": {"path": r"C:\tools\deno.exe"}}


def test_tool_lookup_prefers_tools_dir(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "deno.exe").write_bytes(b"")
    (tools / "ffmpeg.exe").write_bytes(b"")
    monkeypatch.setattr(core, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(core, "resource_dir", lambda: tmp_path)
    assert core.find_js_runtime() == ("deno", str(tools / "deno.exe"))
    assert core.find_ffmpeg() == str(tools / "ffmpeg.exe")


def test_ffmpeg_available():
    assert core.find_ffmpeg()


# --------------------------------------------------------------------------- #
# Fehlerklassifizierung
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("msg, code", [
    ("ERROR: [youtube] abc: Sign in to confirm your age. This video may be inappropriate", "login"),
    ("ERROR: [Instagram] x: Requested content is not available, rate-limit reached or login required", "login"),
    ("ERROR: Private video. Sign in if you've been granted access", "login"),
    ("ERROR: Unsupported URL: https://example.com/", "unsupported"),
    ("ERROR: [youtube] abc: Video unavailable. This video has been removed by the uploader", "unavailable"),
    ("ERROR: [generic] Unable to download webpage: HTTP Error 404: Not Found", "unavailable"),
    ("ERROR: [generic] Unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed>", "network"),
    ("ERROR: Unable to download webpage: The read operation timed out", "network"),
    ("ERROR: Postprocessing: ffprobe and ffmpeg not found. Please install or provide the path", "ffmpeg"),
    ("ERROR: something completely different", "unknown"),
])
def test_classify_error(msg, code):
    assert core.classify_error(msg) == code


def test_classify_cancel():
    assert core.classify_error(core.CancelledByUser()) == "cancelled"


def test_clean_error_message():
    msg = "\x1b[0;31mERROR:\x1b[0m [youtube] abc: Video unavailable; please report this issue on GitHub"
    assert core.clean_error_message(msg) == "abc: Video unavailable"


def test_version_compare():
    assert core.is_newer("2026.11.01", "2026.10.26")
    assert not core.is_newer("2026.10.26", "2026.10.26")
    assert not core.is_newer("2025.1.1", "2026.10.26")


# --------------------------------------------------------------------------- #
# Integration: Analyse und Download über den lokalen Server
# --------------------------------------------------------------------------- #


def test_fetch_info(video_url):
    info = core.fetch_info(video_url)
    assert info.id == "sample"
    assert info.title == "sample"
    assert info.qualities[0] == "best"
    assert "audio" in info.qualities


def test_fetch_info_unsupported(http_server):
    with pytest.raises(core.KestrelgrabError) as exc:
        core.fetch_info(f"{http_server}/page.html")
    assert exc.value.code == "unsupported"


def test_fetch_info_missing(http_server):
    with pytest.raises(core.KestrelgrabError) as exc:
        core.fetch_info(f"{http_server}/missing.mp4")
    assert exc.value.code == "unavailable"


def test_fetch_info_network():
    with pytest.raises(core.KestrelgrabError) as exc:
        core.fetch_info("http://127.0.0.1:9/video.mp4")
    assert exc.value.code == "network"


def test_download_video(video_url, tmp_path):
    events = []
    req = core.DownloadRequest(video_url, str(tmp_path), core.QUALITY_BEST, "mp4")
    path = core.run_download(req, events.append)
    assert Path(path).exists()
    assert Path(path).name == "sample [sample].mp4"
    assert any(e.get("status") == "downloading" for e in events)
    info = probe(path)
    assert info["video"] and info["audio"]


def test_download_mkv(video_url, tmp_path):
    req = core.DownloadRequest(video_url, str(tmp_path), core.QUALITY_BEST, "mkv")
    path = core.run_download(req)
    assert path.endswith(".mkv") and Path(path).exists()


def test_download_mp3_does_not_touch_video(video_url, tmp_path):
    video = core.run_download(core.DownloadRequest(video_url, str(tmp_path), "best", "mp4"))
    events = []
    audio = core.run_download(core.DownloadRequest(video_url, str(tmp_path), "audio", "mp3"),
                              events.append)
    assert Path(audio).name == "sample [sample] (audio).mp3"
    assert Path(video).exists(), "Video darf durch die Audio-Konvertierung nicht gelöscht werden"
    assert any(e.get("status") == "processing" for e in events)
    info = probe(audio)
    assert info["audio"] and not info["video"]
    assert "mp3" in info["raw"]


def test_download_cancel_and_resume(video_url, tmp_path):
    cancel = threading.Event()
    seen = []

    def on_progress(data):
        seen.append(data)
        cancel.set()  # direkt beim ersten Fortschritt abbrechen

    req = core.DownloadRequest(video_url, str(tmp_path), "best", "mp4")
    with pytest.raises(core.KestrelgrabError) as exc:
        core.run_download(req, on_progress, cancel, extra_opts={"ratelimit": 20_000,
                                                                "http_chunk_size": 4096})
    assert exc.value.code == "cancelled"
    assert seen
    assert not list(tmp_path.glob("*.mp4")), "Abgebrochener Download darf keine fertige Datei hinterlassen"

    # Wiederholen funktioniert (Teil-Datei wird fortgesetzt bzw. neu geladen)
    path = core.run_download(req)
    assert Path(path).exists()
    assert not list(tmp_path.glob("*.part"))


def test_download_error_classified(http_server, tmp_path):
    req = core.DownloadRequest(f"{http_server}/missing.mp4", str(tmp_path))
    with pytest.raises(core.KestrelgrabError) as exc:
        core.run_download(req)
    assert exc.value.code == "unavailable"


def test_i18n_complete():
    from app import i18n

    assert i18n.missing_translations() == []
    i18n.set_language("de")
    assert i18n.tr("btn.paste") == "Einfügen"
    i18n.set_language("en")
    assert i18n.tr("btn.paste") == "Paste"
    assert i18n.tr("footer.counts", active=1, waiting=2, done=3) == "1 active, 2 waiting, 3 done"


def test_download_without_console(video_url, tmp_path, monkeypatch):
    """Gepackte --windowed-App: sys.stdout/sys.stderr sind None."""
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    path = core.run_download(core.DownloadRequest(video_url, str(tmp_path), "audio", "m4a"))
    assert path.endswith(" (audio).m4a")
    with pytest.raises(core.KestrelgrabError):
        core.fetch_info("http://127.0.0.1:9/x.mp4")
