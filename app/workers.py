"""Hintergrund-Threads (QThread) für Analyse, Downloads und Update-Prüfung.

Die UI blockiert nie: alle yt-dlp- und Netzwerkaufrufe laufen hier.
"""

from __future__ import annotations

import itertools
import threading
import time
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from . import core

# Threads, deren Besitzer (z. B. ein Dialog) schon geschlossen ist.
_detached: list[QThread] = []


def keep_alive(thread: QThread) -> None:
    """Hält einen laufenden Thread am Leben, bis er fertig ist."""
    thread.setParent(None)
    if thread not in _detached:
        _detached.append(thread)
        thread.finished.connect(lambda t=thread: _detached.remove(t) if t in _detached else None)


def wait_detached(timeout_ms: int = 5000) -> None:
    deadline = time.monotonic() + timeout_ms / 1000
    for t in list(_detached):
        remaining = max(0, int((deadline - time.monotonic()) * 1000))
        if not t.wait(remaining):
            t.terminate()
            t.wait(1000)
    _detached.clear()


# --------------------------------------------------------------------------- #
# Analyse
# --------------------------------------------------------------------------- #


class InfoWorker(QThread):
    succeeded = Signal(int, object, object)  # request_id, MediaInfo, thumbnail bytes|None
    failed = Signal(int, str, str)           # request_id, code, detail

    def __init__(self, request_id: int, url: str, cookies_browser: str | None = None,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.request_id = request_id
        self.url = url
        self.cookies_browser = cookies_browser or None

    def run(self) -> None:
        try:
            info = core.fetch_info(self.url, self.cookies_browser)
        except core.KestrelgrabError as exc:
            self.failed.emit(self.request_id, exc.code, exc.detail)
            return
        except Exception as exc:  # Sicherheitsnetz – niemals Stacktrace in der UI
            err = core.to_kestrelgrab_error(exc)
            self.failed.emit(self.request_id, err.code, err.detail)
            return
        thumb = core.fetch_bytes(info.thumbnail) if info.thumbnail else None
        self.succeeded.emit(self.request_id, info, thumb)


# --------------------------------------------------------------------------- #
# Downloads
# --------------------------------------------------------------------------- #

class JobState:
    WAITING = "waiting"
    RUNNING = "running"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"

    ACTIVE = (RUNNING, PROCESSING)
    FINISHED = (DONE, ERROR, CANCELLED)


_job_ids = itertools.count(1)


class DownloadJob:
    """Zustand eines Downloads (wird nur im UI-Thread verändert)."""

    def __init__(self, request: core.DownloadRequest, title: str = "",
                 thumbnail: bytes | None = None) -> None:
        self.id = next(_job_ids)
        self.request = request
        self.title = title or request.url
        self.thumbnail = thumbnail
        self.state = JobState.WAITING
        self.progress: float | None = 0.0
        self.speed: float | None = None
        self.eta: int | None = None
        self.filepath: str | None = None
        self.error_code: str = ""
        self.error_detail: str = ""

    @property
    def is_active(self) -> bool:
        return self.state in JobState.ACTIVE

    @property
    def is_finished(self) -> bool:
        return self.state in JobState.FINISHED

    def reset(self) -> None:
        self.state = JobState.WAITING
        self.progress = 0.0
        self.speed = None
        self.eta = None
        self.filepath = None
        self.error_code = ""
        self.error_detail = ""


class DownloadWorker(QThread):
    progressed = Signal(object, object)   # job, dict
    succeeded = Signal(object, str)       # job, filepath
    failed = Signal(object, str, str)     # job, code, detail

    MIN_INTERVAL = 0.15  # Sekunden zwischen zwei Fortschrittsmeldungen

    def __init__(self, job: DownloadJob, parent: QObject | None = None,
                 extra_opts: dict[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.cancel_event = threading.Event()
        self.extra_opts = extra_opts
        self._last_emit = 0.0

    def cancel(self) -> None:
        self.cancel_event.set()

    def _on_progress(self, data: dict[str, Any]) -> None:
        now = time.monotonic()
        important = data.get("status") != "downloading" or "title" in data or data.get("progress") == 1.0
        if important or now - self._last_emit >= self.MIN_INTERVAL:
            self._last_emit = now
            self.progressed.emit(self.job, data)

    def run(self) -> None:
        try:
            path = core.run_download(self.job.request, self._on_progress,
                                     self.cancel_event, self.extra_opts)
        except core.KestrelgrabError as exc:
            self.failed.emit(self.job, exc.code, exc.detail)
        except Exception as exc:
            err = core.to_kestrelgrab_error(exc)
            self.failed.emit(self.job, err.code, err.detail)
        else:
            self.succeeded.emit(self.job, path)


class DownloadManager(QObject):
    """Verwaltet die Warteschlange und startet bis zu `max_parallel` Worker."""

    job_added = Signal(object)
    job_changed = Signal(object)
    job_removed = Signal(object)
    counts_changed = Signal(int, int, int)  # aktiv, wartend, fertig

    def __init__(self, max_parallel: int = 2, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.max_parallel = max(1, min(5, max_parallel))
        self.jobs: list[DownloadJob] = []
        self._workers: dict[int, DownloadWorker] = {}
        self._orphans: list[DownloadWorker] = []
        self.extra_opts: dict[str, Any] | None = None  # nur für Tests

    # ----- Öffentliche API ------------------------------------------------- #
    def add(self, request: core.DownloadRequest, title: str = "",
            thumbnail: bytes | None = None) -> DownloadJob:
        job = DownloadJob(request, title, thumbnail)
        self.jobs.append(job)
        self.job_added.emit(job)
        self._schedule()
        self._emit_counts()
        return job

    def cancel(self, job: DownloadJob) -> None:
        worker = self._workers.get(job.id)
        if worker is not None:
            worker.cancel()
        elif job.state == JobState.WAITING:
            job.state = JobState.CANCELLED
            self.job_changed.emit(job)
            self._emit_counts()

    def retry(self, job: DownloadJob) -> None:
        if job.id in self._workers or job not in self.jobs:
            return
        job.reset()
        self.job_changed.emit(job)
        self._schedule()
        self._emit_counts()

    def remove(self, job: DownloadJob) -> None:
        if job not in self.jobs:
            return
        worker = self._workers.pop(job.id, None)
        if worker is not None:
            worker.cancel()
            self._orphans.append(worker)
            worker.finished.connect(lambda w=worker: self._drop_orphan(w))
        self.jobs.remove(job)
        self.job_removed.emit(job)
        self._schedule()
        self._emit_counts()

    def clear_finished(self) -> None:
        for job in [j for j in self.jobs if j.state == JobState.DONE]:
            self.remove(job)

    def set_max_parallel(self, n: int) -> None:
        self.max_parallel = max(1, min(5, int(n)))
        self._schedule()

    def counts(self) -> tuple[int, int, int]:
        active = sum(1 for j in self.jobs if j.is_active)
        waiting = sum(1 for j in self.jobs if j.state == JobState.WAITING)
        done = sum(1 for j in self.jobs if j.state == JobState.DONE)
        return active, waiting, done

    def active_count(self) -> int:
        return self.counts()[0]

    def has_running_threads(self) -> bool:
        return any(w.isRunning() for w in [*self._workers.values(), *self._orphans])

    def shutdown(self, timeout_ms: int = 15000) -> None:
        """Bricht alle Downloads ab und wartet auf das Ende der Threads."""
        workers = [*self._workers.values(), *self._orphans]
        for w in workers:
            w.cancel()
        deadline = time.monotonic() + timeout_ms / 1000
        for w in workers:
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            if not w.wait(remaining):
                # Letzter Ausweg (z. B. hängender ffmpeg-Aufruf)
                w.terminate()
                w.wait(2000)
        self._workers.clear()
        self._orphans.clear()

    # ----- Intern ---------------------------------------------------------- #
    def _emit_counts(self) -> None:
        self.counts_changed.emit(*self.counts())

    def _drop_orphan(self, worker: DownloadWorker) -> None:
        if worker in self._orphans:
            self._orphans.remove(worker)
        worker.deleteLater()

    def _schedule(self) -> None:
        running = len(self._workers)
        for job in self.jobs:
            if running >= self.max_parallel:
                break
            if job.state != JobState.WAITING or job.id in self._workers:
                continue
            worker = DownloadWorker(job, self, self.extra_opts)
            worker.progressed.connect(self._on_progress)
            worker.succeeded.connect(self._on_succeeded)
            worker.failed.connect(self._on_failed)
            worker.finished.connect(self._on_thread_finished)
            self._workers[job.id] = worker
            job.state = JobState.RUNNING
            job.progress = None
            self.job_changed.emit(job)
            worker.start()
            running += 1
        self._emit_counts()

    def _on_progress(self, job: DownloadJob, data: dict) -> None:
        if job.id not in self._workers:
            return
        if data.get("title"):
            job.title = data["title"]
        status = data.get("status")
        job.state = JobState.PROCESSING if status == "processing" else JobState.RUNNING
        job.progress = data.get("progress")
        job.speed = data.get("speed")
        job.eta = data.get("eta")
        self.job_changed.emit(job)

    def _on_succeeded(self, job: DownloadJob, path: str) -> None:
        job.state = JobState.DONE
        job.progress = 1.0
        job.filepath = path
        job.speed = job.eta = None
        self.job_changed.emit(job)

    def _on_failed(self, job: DownloadJob, code: str, detail: str) -> None:
        job.state = JobState.CANCELLED if code == core.ERR_CANCELLED else JobState.ERROR
        job.error_code = code
        job.error_detail = detail
        job.speed = job.eta = None
        self.job_changed.emit(job)

    def _on_thread_finished(self) -> None:
        worker = self.sender()
        for job_id, w in list(self._workers.items()):
            if w is worker:
                del self._workers[job_id]
                w.deleteLater()
                break
        self._schedule()


# --------------------------------------------------------------------------- #
# Update-Prüfung
# --------------------------------------------------------------------------- #

class UpdateCheckWorker(QThread):
    result = Signal(str, str, bool)  # aktuelle Version, neueste Version, ok

    def run(self) -> None:
        current = core.ytdlp_version()
        try:
            latest = core.latest_ytdlp_version()
        except Exception:
            self.result.emit(current, "", False)
            return
        self.result.emit(current, latest, True)


class PipUpdateWorker(QThread):
    result = Signal(bool, str)

    def run(self) -> None:
        try:
            ok, output = core.pip_update_ytdlp()
        except Exception as exc:
            ok, output = False, str(exc)
        self.result.emit(ok, output)
