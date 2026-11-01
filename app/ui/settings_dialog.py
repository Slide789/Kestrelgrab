"""Einstellungsdialog: Sprache, Ordner, Parallelität, Cookies, Komponenten."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .. import core, i18n
from ..i18n import tr
from ..settings import Settings
from ..workers import PipUpdateWorker, UpdateCheckWorker, keep_alive
from .style import repolish


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._update_worker: UpdateCheckWorker | None = None
        self._pip_worker: PipUpdateWorker | None = None
        self._latest: str = ""
        self.setMinimumWidth(560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 18)
        root.setSpacing(6)

        # ----- Allgemein --------------------------------------------------- #
        self.general = QGroupBox()
        form = QFormLayout(self.general)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_language = QLabel()
        self.language = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        form.addRow(self.lbl_language, self.language)

        self.lbl_folder = QLabel()
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.folder = QLineEdit(settings.download_dir)
        self.folder.setMinimumWidth(260)
        self.browse = QPushButton()
        self.browse.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.browse)
        form.addRow(self.lbl_folder, folder_row)

        self.lbl_parallel = QLabel()
        self.parallel = QSpinBox()
        self.parallel.setRange(1, 5)
        self.parallel.setValue(settings.parallel)
        self.parallel.setFixedWidth(90)
        self.parallel.lineEdit().setTextMargins(6, 0, 0, 0)
        form.addRow(self.lbl_parallel, self.parallel)

        self.lbl_cookies = QLabel()
        self.cookies = QComboBox()
        self.cookies.addItem("", "")
        for b in core.COOKIE_BROWSERS:
            self.cookies.addItem(b.capitalize(), b)
        self.cookies.setCurrentIndex(max(0, self.cookies.findData(settings.cookies_browser)))
        cookie_col = QVBoxLayout()
        cookie_col.setSpacing(4)
        cookie_col.addWidget(self.cookies)
        self.cookies_hint = QLabel()
        self.cookies_hint.setObjectName("Muted")
        self.cookies_hint.setWordWrap(True)
        cookie_col.addWidget(self.cookies_hint)
        form.addRow(self.lbl_cookies, cookie_col)
        root.addWidget(self.general)

        # ----- Komponenten ------------------------------------------------- #
        self.components = QGroupBox()
        cform = QFormLayout(self.components)
        cform.setHorizontalSpacing(16)
        cform.setVerticalSpacing(10)

        self.lbl_ytdlp = QLabel()
        ytdlp_col = QVBoxLayout()
        ytdlp_col.setSpacing(6)
        row = QHBoxLayout()
        self.ytdlp_version = QLabel(core.ytdlp_version())
        row.addWidget(self.ytdlp_version)
        row.addStretch(1)
        self.check_btn = QPushButton()
        self.check_btn.clicked.connect(self._check_update)
        row.addWidget(self.check_btn)
        self.update_btn = QPushButton()
        self.update_btn.setProperty("variant", "primary")
        self.update_btn.clicked.connect(self._run_pip_update)
        self.update_btn.hide()
        row.addWidget(self.update_btn)
        ytdlp_col.addLayout(row)
        self.update_status = QLabel()
        self.update_status.setObjectName("Status")
        self.update_status.setWordWrap(True)
        self.update_status.hide()
        ytdlp_col.addWidget(self.update_status)
        cform.addRow(self.lbl_ytdlp, ytdlp_col)

        self.lbl_ffmpeg = QLabel()
        self.ffmpeg_status = QLabel()
        self.ffmpeg_status.setObjectName("Status")
        self.ffmpeg_status.setWordWrap(True)
        self.ffmpeg_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cform.addRow(self.lbl_ffmpeg, self.ffmpeg_status)

        self.lbl_js = QLabel()
        self.js_status = QLabel()
        self.js_status.setObjectName("Status")
        self.js_status.setWordWrap(True)
        self.js_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cform.addRow(self.lbl_js, self.js_status)
        root.addWidget(self.components)

        # ----- Buttons ----------------------------------------------------- #
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 12, 0, 0)
        buttons.addStretch(1)
        self.cancel_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton()
        self.save_btn.setProperty("variant", "primary")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.accept)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.save_btn)
        root.addLayout(buttons)

        self.retranslate()

    # ----- Texte ----------------------------------------------------------- #
    def retranslate(self) -> None:
        self.setWindowTitle(tr("settings.title"))
        self.general.setTitle(tr("settings.general"))
        self.components.setTitle(tr("settings.components"))
        self.lbl_language.setText(tr("settings.language"))
        self.lbl_folder.setText(tr("settings.folder"))
        self.browse.setText(tr("settings.browse"))
        self.lbl_parallel.setText(tr("settings.parallel"))
        self.lbl_cookies.setText(tr("settings.cookies"))
        self.cookies.setItemText(0, tr("settings.cookies_none"))
        self.cookies_hint.setText(tr("settings.cookies_hint"))
        self.lbl_ytdlp.setText(tr("settings.ytdlp"))
        self.check_btn.setText(tr("settings.check_update"))
        self.update_btn.setText(tr("settings.update_now"))
        self.lbl_ffmpeg.setText(tr("settings.ffmpeg"))
        self.lbl_js.setText(tr("settings.js"))
        self.cancel_btn.setText(tr("settings.cancel"))
        self.save_btn.setText(tr("settings.save"))
        self._refresh_components()

    def _set_status(self, label: QLabel, text: str, kind: str) -> None:
        label.setText(text)
        label.setProperty("kind", kind)
        repolish(label)
        label.show()

    def _refresh_components(self) -> None:
        ffmpeg = core.find_ffmpeg()
        if ffmpeg:
            self._set_status(self.ffmpeg_status, tr("settings.found", path=ffmpeg), "ok")
        else:
            self._set_status(self.ffmpeg_status, tr("settings.not_found"), "error")
        runtime = core.find_js_runtime()
        if runtime:
            name, path = runtime
            self._set_status(self.js_status, tr("settings.found", path=f"{name} – {path}"), "ok")
        else:
            self._set_status(self.js_status,
                             f"{tr('settings.not_found')}. {tr('settings.js_missing_hint')}", "error")

    # ----- Aktionen -------------------------------------------------------- #
    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("settings.choose_folder"), self.folder.text())
        if path:
            self.folder.setText(path.replace("/", "\\"))

    def _check_update(self) -> None:
        if self._update_worker and self._update_worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.update_btn.hide()
        self._set_status(self.update_status, tr("settings.checking"), "info")
        self._update_worker = UpdateCheckWorker(self)
        self._update_worker.result.connect(self._on_update_result)
        self._update_worker.start()

    def _on_update_result(self, current: str, latest: str, ok: bool) -> None:
        self.check_btn.setEnabled(True)
        if not ok:
            self._set_status(self.update_status, tr("settings.update_failed"), "error")
            return
        self._latest = latest
        if core.is_newer(latest, current):
            if core.is_frozen():
                self._set_status(self.update_status, tr("settings.update_frozen", v=latest), "info")
            else:
                self._set_status(self.update_status, tr("settings.update_available", v=latest), "info")
                self.update_btn.show()
        else:
            self._set_status(self.update_status, tr("settings.up_to_date", v=current), "ok")

    def _run_pip_update(self) -> None:
        if core.is_frozen() or (self._pip_worker and self._pip_worker.isRunning()):
            return
        self.update_btn.setEnabled(False)
        self.check_btn.setEnabled(False)
        self._set_status(self.update_status, tr("settings.updating"), "info")
        self._pip_worker = PipUpdateWorker(self)
        self._pip_worker.result.connect(self._on_pip_result)
        self._pip_worker.start()

    def _on_pip_result(self, ok: bool, output: str) -> None:
        self.check_btn.setEnabled(True)
        self.update_btn.setEnabled(True)
        if ok:
            self.update_btn.hide()
            self._set_status(self.update_status, tr("settings.updated"), "ok")
        else:
            self._set_status(self.update_status, tr("settings.update_error"), "error")
            self.update_status.setToolTip(output[-800:])

    # ----- Ergebnis -------------------------------------------------------- #
    def values(self) -> dict:
        return {
            "language": self.language.currentData(),
            "download_dir": self.folder.text().strip(),
            "parallel": self.parallel.value(),
            "cookies_browser": self.cookies.currentData() or "",
        }

    def done(self, result: int) -> None:  # noqa: D401 – Qt-API
        # Laufende Threads dürfen den Dialog überleben, ohne die UI zu blockieren.
        for w in (self._update_worker, self._pip_worker):
            if w is not None and w.isRunning():
                w.result.disconnect()
                keep_alive(w)
        super().done(result)
