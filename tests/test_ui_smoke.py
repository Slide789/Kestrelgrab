"""UI-Smoketest (QT_QPA_PLATFORM=offscreen)."""

from __future__ import annotations

import os
import time
import uuid

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import i18n  # noqa: E402
from app.settings import Settings  # noqa: E402
from app.workers import JobState  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from app.ui.style import build_stylesheet

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(build_stylesheet())
    yield app


@pytest.fixture
def window(qapp, tmp_path):
    from app.ui.main_window import MainWindow

    ini = tmp_path / f"settings-{uuid.uuid4().hex}.ini"
    settings = Settings(QSettings(str(ini), QSettings.Format.IniFormat))
    settings.download_dir = str(tmp_path / "downloads")
    settings.language = "de"
    i18n.set_language("de")
    win = MainWindow(settings)
    win.show()
    qapp.processEvents()
    yield win
    win.shutdown()
    win.close()
    win.deleteLater()
    qapp.processEvents()


def wait_until(app, predicate, timeout=60.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    app.processEvents()
    return predicate()


def test_window_and_language_switch(qapp, window):
    assert window.minimumWidth() == 820 and window.minimumHeight() == 600
    assert window.paste_btn.text() == "Einfügen"
    assert "aktiv" in window.counts_label.text()
    assert window.queue_stack.currentIndex() == 0  # Leerzustand
    assert window.empty_label.text()

    i18n.set_language("en")
    qapp.processEvents()
    assert window.paste_btn.text() == "Paste"
    assert window.counts_label.text() == "0 active, 0 waiting, 0 done"
    assert "rights" in window.legal_label.text()

    i18n.set_language("de")
    qapp.processEvents()
    assert window.analyze_btn.text() == "Analysieren"


def test_invalid_input_shows_error(qapp, window):
    window.url_input.setText("kein link")
    window.submit_input()
    assert window.status.isVisible()
    assert window.status.property("kind") == "error"


def test_analyze_and_download(qapp, window, video_url, tmp_path):
    window.url_input.setText(video_url.replace("http://", "http://"))
    window.submit_input()
    assert wait_until(qapp, lambda: window.preview.isVisible(), 30), window.status.text()
    assert window.preview.title.text() == "sample"
    qualities = [window.preview.quality.itemData(i) for i in range(window.preview.quality.count())]
    assert qualities[0] == "best" and "audio" in qualities

    # Audio wählen → Formatliste wechselt auf Audioformate
    window.preview.quality.setCurrentIndex(qualities.index("audio"))
    formats = [window.preview.format.itemData(i) for i in range(window.preview.format.count())]
    assert formats == ["mp3", "m4a", "opus", "flac", "wav"]
    window.preview.quality.setCurrentIndex(0)
    formats = [window.preview.format.itemData(i) for i in range(window.preview.format.count())]
    assert formats == ["mp4", "mkv", "webm"]

    window.download_preview()
    assert len(window.manager.jobs) == 1
    job = window.manager.jobs[0]
    assert window.queue_stack.currentIndex() == 1
    assert wait_until(qapp, lambda: job.is_finished, 60), job.state
    assert job.state == JobState.DONE, (job.error_code, job.error_detail)
    assert os.path.exists(job.filepath)
    card = window.cards[job.id]
    assert card.btn_open.isVisibleTo(card) and card.btn_folder.isVisibleTo(card)
    assert "1 fertig" in window.counts_label.text()

    window.manager.clear_finished()
    qapp.processEvents()
    assert not window.manager.jobs
    assert window.queue_stack.currentIndex() == 0


def test_multiple_links_go_to_queue(qapp, window, video_url, http_server):
    window.settings.audio_format = "m4a"
    window.handle_text(f"{video_url}\n{http_server}/missing.mp4")
    assert len(window.manager.jobs) == 2
    assert wait_until(qapp, lambda: all(j.is_finished for j in window.manager.jobs), 60)
    ok, bad = window.manager.jobs
    assert ok.state == JobState.DONE
    assert bad.state == JobState.ERROR and bad.error_code == "unavailable"
    # Fehler übersetzt, kein Stacktrace
    text = window.cards[bad.id].status.text()
    assert "Traceback" not in text and "verfügbar" in text

    # Wiederholen startet den Job erneut
    window.manager.retry(bad)
    assert bad.state in (JobState.WAITING, JobState.RUNNING)
    assert wait_until(qapp, lambda: bad.is_finished, 30)

    window.manager.remove(bad)
    qapp.processEvents()
    assert bad.id not in window.cards


def test_cancel_job(qapp, window, video_url):
    window.manager.extra_opts = {"ratelimit": 15_000, "http_chunk_size": 4096}
    window.enqueue(video_url)
    job = window.manager.jobs[-1]
    assert wait_until(qapp, lambda: job.state == JobState.RUNNING and job.progress, 30)
    window.manager.cancel(job)
    assert wait_until(qapp, lambda: job.is_finished, 30)
    assert job.state == JobState.CANCELLED
    card = window.cards[job.id]
    assert card.btn_retry.isVisibleTo(card)


def test_parallel_limit(qapp, window, video_url):
    window.manager.extra_opts = {"ratelimit": 30_000}
    window.manager.set_max_parallel(1)
    for _ in range(3):
        window.enqueue(video_url)
    qapp.processEvents()
    active, waiting, _ = window.manager.counts()
    assert active <= 1 and waiting >= 2
    for j in window.manager.jobs:
        window.manager.cancel(j)
    assert wait_until(qapp, lambda: not window.manager.has_running_threads(), 30)


def test_settings_dialog(qapp, window):
    dialog = window.open_settings()
    qapp.processEvents()
    assert dialog.isVisible()
    assert dialog.windowTitle() == "Einstellungen"
    assert dialog.parallel.minimum() == 1 and dialog.parallel.maximum() == 5
    assert dialog.cookies.count() == 7
    assert dialog.ffmpeg_status.property("kind") == "ok"

    dialog.language.setCurrentIndex(dialog.language.findData("en"))
    dialog.parallel.setValue(4)
    dialog.accept()
    qapp.processEvents()
    assert window.settings.parallel == 4
    assert window.manager.max_parallel == 4
    assert i18n.current_language() == "en"
    assert window.paste_btn.text() == "Paste"


def test_default_language_is_english(tmp_path):
    ini = tmp_path / "fresh.ini"
    assert Settings(QSettings(str(ini), QSettings.Format.IniFormat)).language == "en"
