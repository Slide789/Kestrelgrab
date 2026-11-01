"""Hauptfenster von Kestrelgrab."""

from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import APP_NAME, core, i18n
from ..i18n import tr
from ..settings import Settings
from ..workers import DownloadJob, DownloadManager, InfoWorker, wait_detached
from .settings_dialog import SettingsDialog
from .style import repolish
from .widgets import DownloadCard, ElidedLabel, PreviewCard, error_text


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings | None = None, icon: QIcon | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self.has_ffmpeg = core.find_ffmpeg() is not None
        self.manager = DownloadManager(self.settings.parallel, self)
        self.cards: dict[int, DownloadCard] = {}
        self._info_request = 0
        self._info_workers: list[InfoWorker] = []
        self._settings_dialog: SettingsDialog | None = None
        self._closing = False

        self.setWindowTitle(APP_NAME)
        if icon is not None:
            self.setWindowIcon(icon)
        self.setMinimumSize(820, 600)
        self.resize(980, 720)
        self.setAcceptDrops(True)

        self._build_ui(icon)
        self._connect()

        geometry = self.settings.geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)

        i18n.on_change(self.retranslate)
        self.retranslate()
        self._update_counts(*self.manager.counts())

    # ------------------------------------------------------------------ #
    # Aufbau
    # ------------------------------------------------------------------ #
    def _build_ui(self, icon: QIcon | None) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 14)
        layout.setSpacing(14)

        # Kopfzeile
        header = QHBoxLayout()
        header.setSpacing(12)
        self.logo = QLabel()
        if icon is not None and not icon.isNull():
            self.logo.setPixmap(icon.pixmap(QSize(40, 40)))
        self.logo.setFixedSize(40, 40)
        header.addWidget(self.logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.app_title = QLabel(APP_NAME)
        self.app_title.setObjectName("AppTitle")
        self.subtitle = ElidedLabel()
        self.subtitle.setObjectName("Subtitle")
        titles.addWidget(self.app_title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles, 1)
        self.settings_btn = QPushButton()
        self.settings_btn.setProperty("variant", "ghost")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        # Warnbanner (ffmpeg fehlt)
        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        banner_layout.addWidget(self.banner_text)
        self.banner.setVisible(not self.has_ffmpeg)
        layout.addWidget(self.banner)

        # Eingabe
        input_card = QFrame()
        input_card.setObjectName("Card")
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 16, 16, 12)
        input_layout.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("UrlInput")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setAcceptDrops(False)  # Drops übernimmt das Fenster
        row.addWidget(self.url_input, 1)
        self.paste_btn = QPushButton()
        self.paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_btn.setMinimumHeight(40)
        row.addWidget(self.paste_btn)
        self.analyze_btn = QPushButton()
        self.analyze_btn.setProperty("variant", "primary")
        self.analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_btn.setMinimumHeight(40)
        row.addWidget(self.analyze_btn)
        input_layout.addLayout(row)
        self.status = QLabel()
        self.status.setObjectName("Status")
        self.status.setWordWrap(True)
        self.status.hide()
        input_layout.addWidget(self.status)
        layout.addWidget(input_card)

        # Vorschau
        self.preview = PreviewCard()
        self.preview.set_defaults(self.settings.video_format, self.settings.audio_format, self.has_ffmpeg)
        self.preview.hide()
        layout.addWidget(self.preview)

        # Warteschlange
        queue_header = QHBoxLayout()
        self.queue_title = QLabel()
        self.queue_title.setObjectName("SectionTitle")
        queue_header.addWidget(self.queue_title)
        queue_header.addStretch(1)
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setProperty("variant", "ghost")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        queue_header.addWidget(self.open_folder_btn)
        self.clear_btn = QPushButton()
        self.clear_btn.setProperty("variant", "ghost")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        queue_header.addWidget(self.clear_btn)
        layout.addLayout(queue_header)

        self.queue_stack = QStackedWidget()
        self.queue_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("EmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty = QFrame()
        empty.setObjectName("Card")
        empty_layout = QVBoxLayout(empty)
        empty_layout.addWidget(self.empty_label)
        self.queue_stack.addWidget(empty)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.queue_container = QWidget()
        self.queue_container.setObjectName("QueueContainer")
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 6, 0)
        self.queue_layout.setSpacing(8)
        self.queue_layout.addStretch(1)
        self.scroll.setWidget(self.queue_container)
        self.queue_stack.addWidget(self.scroll)
        layout.addWidget(self.queue_stack, 1)

        # Fußzeile
        footer = QHBoxLayout()
        footer.setSpacing(16)
        self.counts_label = QLabel()
        self.counts_label.setObjectName("Footer")
        footer.addWidget(self.counts_label)
        footer.addStretch(1)
        self.legal_label = QLabel()
        self.legal_label.setObjectName("Legal")
        self.legal_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.legal_label.setWordWrap(True)
        footer.addWidget(self.legal_label, 2)
        layout.addLayout(footer)

    def _connect(self) -> None:
        self.settings_btn.clicked.connect(self.open_settings)
        self.paste_btn.clicked.connect(self.paste_from_clipboard)
        self.analyze_btn.clicked.connect(self.submit_input)
        self.url_input.returnPressed.connect(self.submit_input)
        self.preview.download_requested.connect(self.download_preview)
        self.preview.close_requested.connect(self._hide_preview)
        self.clear_btn.clicked.connect(self.manager.clear_finished)
        self.open_folder_btn.clicked.connect(self.open_download_folder)

        self.manager.job_added.connect(self._on_job_added)
        self.manager.job_changed.connect(self._on_job_changed)
        self.manager.job_removed.connect(self._on_job_removed)
        self.manager.counts_changed.connect(self._update_counts)

        QShortcut(QKeySequence("Ctrl+,"), self, activated=self.open_settings)

    # ------------------------------------------------------------------ #
    # Texte
    # ------------------------------------------------------------------ #
    def retranslate(self) -> None:
        self.subtitle.setText(tr("app.subtitle"))
        self.settings_btn.setText("⚙  " + tr("btn.settings"))
        self.banner_text.setText(tr("banner.no_ffmpeg"))
        self.url_input.setPlaceholderText(tr("input.placeholder"))
        self.paste_btn.setText(tr("btn.paste"))
        self.analyze_btn.setText(tr("btn.analyze"))
        self.queue_title.setText(tr("queue.title"))
        self.clear_btn.setText(tr("queue.clear_done"))
        self.open_folder_btn.setText(tr("settings.folder"))
        self.empty_label.setText(tr("queue.empty"))
        self.legal_label.setText(tr("footer.legal"))
        self.preview.retranslate()
        for card in self.cards.values():
            card.retranslate()
        self._update_counts(*self.manager.counts())
        if self._status_key:
            key, kind, detail, kwargs = self._status_key
            self._show_status(key, kind, detail, **kwargs)

    _status_key: tuple | None = None

    def _show_status(self, key: str, kind: str = "info", detail: str = "", **kwargs) -> None:
        """Zeigt eine (übersetzbare) Statuszeile unter dem Eingabefeld."""
        self._status_key = (key, kind, detail, kwargs)
        text = error_text(key[6:]) if key.startswith("error.") else tr(key, **kwargs)
        self.status.setText(text)
        self.status.setToolTip(tr("error.details", detail=detail) if detail else "")
        self.status.setProperty("kind", kind)
        repolish(self.status)
        self.status.show()

    def _hide_status(self) -> None:
        self._status_key = None
        self.status.hide()

    # ------------------------------------------------------------------ #
    # Eingabe
    # ------------------------------------------------------------------ #
    def paste_from_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text() or ""
        if not core.extract_urls(text):
            self._show_status("status.clipboard_empty", "error")
            return
        self.handle_text(text)

    def submit_input(self) -> None:
        self.handle_text(self.url_input.text())

    def handle_text(self, text: str) -> None:
        """Ein Link → analysieren; mehrere Links → direkt in die Warteschlange."""
        urls = core.extract_urls(text)
        if not urls:
            self._show_status("status.no_link", "error")
            return
        if len(urls) == 1:
            self.url_input.setText(urls[0])
            self.analyze(urls[0])
            return
        for url in urls:
            self.enqueue(url)
        self.url_input.clear()
        self._show_status("status.queued_many", "ok", n=len(urls))

    def analyze(self, url: str) -> None:
        self._info_request += 1
        request_id = self._info_request
        self.preview.hide()
        self._show_status("status.analyzing", "info")
        self.analyze_btn.setEnabled(False)
        worker = InfoWorker(request_id, url, self.settings.cookies_browser, self)
        worker.succeeded.connect(self._on_info)
        worker.failed.connect(self._on_info_failed)
        worker.finished.connect(lambda w=worker: self._drop_info_worker(w))
        self._info_workers.append(worker)
        worker.start()

    def _drop_info_worker(self, worker: InfoWorker) -> None:
        if worker in self._info_workers:
            self._info_workers.remove(worker)
            worker.deleteLater()

    def _on_info(self, request_id: int, info: core.MediaInfo, thumb) -> None:
        if request_id != self._info_request or self._closing:
            return
        self.analyze_btn.setEnabled(True)
        self._hide_status()
        self.preview.set_info(info, thumb)
        self.preview.show()

    def _on_info_failed(self, request_id: int, code: str, detail: str) -> None:
        if request_id != self._info_request or self._closing:
            return
        self.analyze_btn.setEnabled(True)
        self._show_status(f"error.{code}", "error", detail)

    def _hide_preview(self) -> None:
        self.preview.hide()
        self.preview.info = None

    # ------------------------------------------------------------------ #
    # Warteschlange
    # ------------------------------------------------------------------ #
    def _effective_format(self, audio: bool, fmt: str) -> str:
        if not self.has_ffmpeg:
            return ""
        if fmt:
            return fmt
        return self.settings.audio_format if audio else self.settings.video_format

    def enqueue(self, url: str, quality: str | int = core.QUALITY_BEST, fmt: str = "",
                title: str = "", thumbnail: bytes | None = None, portrait: bool = False) -> DownloadJob:
        audio = quality == core.QUALITY_AUDIO
        request = core.DownloadRequest(
            url=url,
            folder=self.settings.download_dir,
            quality=quality,
            fmt=self._effective_format(audio, fmt),
            cookies_browser=self.settings.cookies_browser or None,
            portrait=portrait,
        )
        return self.manager.add(request, title, thumbnail)

    def download_preview(self) -> None:
        info = self.preview.info
        if info is None:
            return
        quality, fmt = self.preview.selection()
        if fmt:
            if quality == core.QUALITY_AUDIO:
                self.settings.audio_format = fmt
            else:
                self.settings.video_format = fmt
        self.enqueue(info.url, quality, fmt, info.title, self.preview.thumb_bytes, info.portrait)
        self._hide_preview()
        self.url_input.clear()
        self._show_status("status.queued_one", "ok")

    def _on_job_added(self, job: DownloadJob) -> None:
        card = DownloadCard(job)
        card.cancel_clicked.connect(self.manager.cancel)
        card.retry_clicked.connect(self.manager.retry)
        card.remove_clicked.connect(self.manager.remove)
        card.open_clicked.connect(self.open_file)
        card.folder_clicked.connect(self.show_in_folder)
        self.cards[job.id] = card
        self.queue_layout.insertWidget(self.queue_layout.count() - 1, card)
        self.queue_stack.setCurrentIndex(1)
        QTimer.singleShot(0, lambda: self.scroll.ensureWidgetVisible(card))

    def _on_job_changed(self, job: DownloadJob) -> None:
        card = self.cards.get(job.id)
        if card is not None:
            card.refresh()

    def _on_job_removed(self, job: DownloadJob) -> None:
        card = self.cards.pop(job.id, None)
        if card is not None:
            self.queue_layout.removeWidget(card)
            card.deleteLater()
        if not self.cards:
            self.queue_stack.setCurrentIndex(0)

    def _update_counts(self, active: int, waiting: int, done: int) -> None:
        self.counts_label.setText(tr("footer.counts", active=active, waiting=waiting, done=done))
        self.clear_btn.setEnabled(done > 0)

    # ------------------------------------------------------------------ #
    # Dateien
    # ------------------------------------------------------------------ #
    def open_file(self, job: DownloadJob) -> None:
        if job.filepath and os.path.exists(job.filepath):
            QDesktopServices.openUrl(QUrl.fromLocalFile(job.filepath))
        else:
            QMessageBox.information(self, APP_NAME, tr("job.file_missing"))

    def show_in_folder(self, job: DownloadJob) -> None:
        path = job.filepath
        if not path or not os.path.exists(path):
            QMessageBox.information(self, APP_NAME, tr("job.file_missing"))
            return
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def open_download_folder(self) -> None:
        folder = self.settings.download_dir
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # ------------------------------------------------------------------ #
    # Einstellungen
    # ------------------------------------------------------------------ #
    def open_settings(self) -> SettingsDialog:
        dialog = SettingsDialog(self.settings, self)
        self._settings_dialog = dialog
        dialog.accepted.connect(lambda: self._apply_settings(dialog.values()))
        dialog.finished.connect(lambda _=0: setattr(self, "_settings_dialog", None))
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.open()
        return dialog

    def _apply_settings(self, values: dict) -> None:
        self.settings.download_dir = values["download_dir"] or self.settings.download_dir
        self.settings.parallel = values["parallel"]
        self.settings.cookies_browser = values["cookies_browser"]
        self.settings.language = values["language"]
        self.settings.sync()
        self.manager.set_max_parallel(self.settings.parallel)
        i18n.set_language(values["language"])

    # ------------------------------------------------------------------ #
    # Drag & Drop
    # ------------------------------------------------------------------ #
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        parts = []
        if mime.hasUrls():
            parts.extend(u.toString() for u in mime.urls() if not u.isLocalFile())
        if mime.hasText():
            parts.append(mime.text())
        self.handle_text("\n".join(parts))
        event.acceptProposedAction()

    # ------------------------------------------------------------------ #
    # Schließen
    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:  # noqa: N802
        active = self.manager.active_count()
        if active and not self._closing:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(tr("close.title"))
            box.setText(tr("close.text", n=active))
            quit_btn = box.addButton(tr("close.quit"), QMessageBox.ButtonRole.AcceptRole)
            stay_btn = box.addButton(tr("close.stay"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(stay_btn)
            box.exec()
            if box.clickedButton() is not quit_btn:
                event.ignore()
                return
        self.shutdown()
        event.accept()

    def shutdown(self) -> None:
        """Beendet alle Worker sauber (wird auch von Tests genutzt)."""
        if self._closing:
            return
        self._closing = True
        self.settings.set_geometry(self.saveGeometry())
        self.settings.sync()
        i18n.remove_listener(self.retranslate)
        self.manager.shutdown(15000)
        for worker in list(self._info_workers):
            if not worker.wait(5000):
                worker.terminate()
                worker.wait(1000)
        self._info_workers.clear()
        wait_detached(5000)
