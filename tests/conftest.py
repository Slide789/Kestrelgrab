"""Gemeinsame Fixtures: Testvideo (per ffmpeg erzeugt) und lokaler HTTP-Server."""

from __future__ import annotations

import functools
import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def handle(self) -> None:
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass


@pytest.fixture(scope="session")
def media_dir(tmp_path_factory) -> Path:
    import imageio_ffmpeg

    d = tmp_path_factory.mktemp("media")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = d / "sample.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(video)],
        check=True,
    )
    (d / "page.html").write_text("<html><body><p>Kein Video hier.</p></body></html>", encoding="utf-8")
    return d


@pytest.fixture(scope="session")
def http_server(media_dir):
    handler = functools.partial(_QuietHandler, directory=str(media_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def video_url(http_server) -> str:
    return f"{http_server}/sample.mp4"
