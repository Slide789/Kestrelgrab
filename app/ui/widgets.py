"""Vorschau-Karte, Download-Karten und kleine Hilfs-Widgets."""

from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy,
    QToolButton, QVBoxLayout, QWidget,
)

from .. import core
from ..i18n import tr
from ..workers import DownloadJob, JobState
from .style import pixmap_from_bytes, placeholder_pixmap, repolish, rounded_pixmap

# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #


def human_bytes(n: float | None) -> str:
    if not n or n < 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def human_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    return core.format_duration(max(1, seconds)) or "0:01"


def quality_label(q: str | int) -> str:
    if q == core.QUALITY_BEST:
        return tr("quality.best")
    if q == core.QUALITY_AUDIO:
        return tr("quality.audio")
    return f"{q}p"


def error_text(code: str) -> str:
    key = f"error.{code}"
    text = tr(key)
    return text if text != key else tr("error.unknown")


class ElidedLabel(QLabel):
    """Einzeiliges Label, das zu langen Text mit „…“ kürzt."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)

    def minimumSizeHint(self) -> QSize:
        return QSize(40, super().minimumSizeHint().height())

    def paintEvent(self, event) -> None:  # noqa: N802 – Qt-API
        painter = QPainter(self)
        rect = self.contentsRect()
        elided = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, rect.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, int(self.alignment()) | Qt.AlignmentFlag.AlignVCenter, elided)
        painter.end()

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self.setToolTip(text if text else "")


class ThumbLabel(QLabel):
    def __init__(self, width: int, height: int, radius: float, parent: QWidget | None = None):
        super().__init__(parent)
        self._w, self._h, self._r = width, height, radius
        self.setFixedSize(width, height)
        self._source: QPixmap | None = None
        self._audio = False
        self._render()

    def set_source(self, data: bytes | QPixmap | None, audio: bool = False) -> None:
        self._source = data if isinstance(data, QPixmap) else pixmap_from_bytes(data)
        self._audio = audio
        self._render()

    def _render(self) -> None:
        ratio = self.devicePixelRatioF() or 1.0
        if self._source is not None:
            self.setPixmap(rounded_pixmap(self._source, self._w, self._h, self._r, ratio))
        else:
            self.setPixmap(placeholder_pixmap(self._w, self._h, self._r, self._audio, ratio))


def _set_kind(label: QLabel, kind: str) -> None:
    if label.property("kind") != kind:
        label.setProperty("kind", kind)
        repolish(label)


# --------------------------------------------------------------------------- #
# Vorschau-Karte
# --------------------------------------------------------------------------- #


class PreviewCard(QFrame):
    download_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.info: core.MediaInfo | None = None
        self.thumb_bytes: bytes | None = None
        self._video_fmt = "mp4"
        self._audio_fmt = "mp3"
        self._has_ffmpeg = True

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        self.thumb = ThumbLabel(208, 117, 10)
        root.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignTop)

        right = QVBoxLayout()
        right.setSpacing(6)
        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("PreviewTitle")
        self.title.setWordWrap(True)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        top.addWidget(self.title, 1)
        self.close_btn = QToolButton()
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setText("✕")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.close_requested)
        top.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignTop)
        right.addLayout(top)

        self.meta = ElidedLabel()
        self.meta.setObjectName("Meta")
        right.addWidget(self.meta)
        right.addStretch(1)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        q_box = QVBoxLayout()
        q_box.setSpacing(3)
        self.quality_label = QLabel()
        self.quality_label.setObjectName("FieldLabel")
        self.quality = QComboBox()
        self.quality.setMinimumWidth(150)
        q_box.addWidget(self.quality_label)
        q_box.addWidget(self.quality)
        controls.addLayout(q_box)

        f_box = QVBoxLayout()
        f_box.setSpacing(3)
        self.format_label = QLabel()
        self.format_label.setObjectName("FieldLabel")
        self.format = QComboBox()
        self.format.setMinimumWidth(100)
        f_box.addWidget(self.format_label)
        f_box.addWidget(self.format)
        controls.addLayout(f_box)
        controls.addStretch(1)

        self.download_btn = QPushButton()
        self.download_btn.setProperty("variant", "primary")
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.setMinimumHeight(36)
        self.download_btn.clicked.connect(self.download_requested)
        controls.addWidget(self.download_btn, 0, Qt.AlignmentFlag.AlignBottom)
        right.addLayout(controls)
        root.addLayout(right, 1)

        self.quality.currentIndexChanged.connect(self._on_quality_changed)
        self.format.currentIndexChanged.connect(self._on_format_changed)
        self.retranslate()

    # ----- Daten ----------------------------------------------------------- #
    def set_defaults(self, video_fmt: str, audio_fmt: str, has_ffmpeg: bool) -> None:
        self._video_fmt = video_fmt
        self._audio_fmt = audio_fmt
        self._has_ffmpeg = has_ffmpeg

    def set_info(self, info: core.MediaInfo, thumb: bytes | None) -> None:
        self.info = info
        self.thumb_bytes = thumb
        self.thumb.set_source(thumb)
        self.title.setText(info.title)
        self.title.setToolTip(info.url)
        self._fill_quality()
        self._update_meta()

    def _update_meta(self) -> None:
        if not self.info:
            return
        parts = [self.info.uploader or tr("preview.unknown_uploader")]
        if self.info.duration_text:
            parts.append(self.info.duration_text)
        if self.info.extractor:
            parts.append(self.info.extractor)
        self.meta.setText("  ·  ".join(parts))

    def _fill_quality(self) -> None:
        current = self.quality.currentData()
        self.quality.blockSignals(True)
        self.quality.clear()
        for q in (self.info.qualities if self.info else [core.QUALITY_BEST]):
            self.quality.addItem(quality_label(q), q)
        idx = self.quality.findData(current) if current is not None else -1
        self.quality.setCurrentIndex(max(0, idx))
        self.quality.blockSignals(False)
        self._fill_format()

    def _fill_format(self) -> None:
        audio = self.quality.currentData() == core.QUALITY_AUDIO
        self.format.blockSignals(True)
        self.format.clear()
        if not self._has_ffmpeg:
            # Ohne ffmpeg keine Umwandlung – Datei wird im Originalformat geladen.
            self.format.addItem("Original", "")
            self.format.setEnabled(False)
        else:
            self.format.setEnabled(True)
            options = core.AUDIO_FORMATS if audio else core.VIDEO_FORMATS
            for f in options:
                self.format.addItem(f.upper(), f)
            wanted = self._audio_fmt if audio else self._video_fmt
            self.format.setCurrentIndex(max(0, self.format.findData(wanted)))
        self.format.blockSignals(False)
        self.thumb.set_source(self.thumb_bytes, audio)

    def _on_quality_changed(self) -> None:
        self._fill_format()

    def _on_format_changed(self) -> None:
        fmt = self.format.currentData()
        if not fmt:
            return
        if self.quality.currentData() == core.QUALITY_AUDIO:
            self._audio_fmt = fmt
        else:
            self._video_fmt = fmt

    def selection(self) -> tuple[str | int, str]:
        q = self.quality.currentData()
        fmt = self.format.currentData() or ""
        return (q if q is not None else core.QUALITY_BEST), fmt

    # ----- Texte ----------------------------------------------------------- #
    def retranslate(self) -> None:
        self.quality_label.setText(tr("preview.quality"))
        self.format_label.setText(tr("preview.format"))
        self.download_btn.setText(tr("btn.download"))
        for i in range(self.quality.count()):
            self.quality.setItemText(i, quality_label(self.quality.itemData(i)))
        self._update_meta()


# --------------------------------------------------------------------------- #
# Download-Karte
# --------------------------------------------------------------------------- #


class DownloadCard(QFrame):
    cancel_clicked = Signal(object)
    retry_clicked = Signal(object)
    open_clicked = Signal(object)
    folder_clicked = Signal(object)
    remove_clicked = Signal(object)

    def __init__(self, job: DownloadJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.setObjectName("JobCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(14)

        self.thumb = ThumbLabel(112, 63, 8)
        self.thumb.set_source(job.thumbnail, job.request.is_audio)
        root.addWidget(self.thumb, 0, Qt.AlignmentFlag.AlignVCenter)

        mid = QVBoxLayout()
        mid.setSpacing(5)
        self.title = ElidedLabel()
        self.title.setObjectName("JobTitle")
        mid.addWidget(self.title)

        line = QHBoxLayout()
        line.setSpacing(8)
        self.badge = ElidedLabel()
        self.badge.setObjectName("Meta")
        self.badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        line.addWidget(self.badge)
        self.status = ElidedLabel()
        self.status.setObjectName("JobStatus")
        line.addWidget(self.status, 1)
        mid.addLayout(line)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 1000)
        mid.addWidget(self.bar)
        root.addLayout(mid, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        self.btn_cancel = self._tool(buttons, lambda: self.cancel_clicked.emit(self.job), "danger")
        self.btn_retry = self._tool(buttons, lambda: self.retry_clicked.emit(self.job), "accent")
        self.btn_open = self._tool(buttons, lambda: self.open_clicked.emit(self.job), "accent")
        self.btn_folder = self._tool(buttons, lambda: self.folder_clicked.emit(self.job))
        self.btn_remove = self._tool(buttons, lambda: self.remove_clicked.emit(self.job), "danger")
        root.addLayout(buttons)

        self.retranslate()

    @staticmethod
    def _tool(layout: QHBoxLayout, slot, variant: str = "") -> QToolButton:
        btn = QToolButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if variant:
            btn.setProperty("variant", variant)
        btn.clicked.connect(slot)
        layout.addWidget(btn)
        return btn

    def retranslate(self) -> None:
        self.btn_cancel.setText(tr("job.cancel"))
        self.btn_retry.setText(tr("job.retry"))
        self.btn_open.setText(tr("job.open"))
        self.btn_folder.setText(tr("job.folder"))
        self.btn_remove.setText(tr("job.remove"))
        self.refresh()

    def _badge_text(self) -> str:
        req = self.job.request
        fmt = (req.fmt or "").upper() or "Original"
        if req.is_audio:
            return f"{fmt} · {tr('quality.audio')}"
        return f"{fmt} · {quality_label(req.quality)}"

    def refresh(self) -> None:
        job = self.job
        self.title.setText(job.title)
        self.badge.setText(self._badge_text())
        state = job.state

        bar_state = ""
        if state == JobState.WAITING:
            text, kind = tr("job.waiting"), "info"
            self.bar.setRange(0, 1000)
            self.bar.setValue(0)
        elif state == JobState.RUNNING:
            kind = "info"
            if job.progress is None:
                self.bar.setRange(0, 0)  # unbestimmt
                text = tr("job.starting") if not job.speed else tr("job.downloading")
            else:
                self.bar.setRange(0, 1000)
                self.bar.setValue(int(job.progress * 1000))
                text = f"{tr('job.downloading')} · {job.progress * 100:.0f} %"
            extras = []
            if job.speed:
                extras.append(f"{human_bytes(job.speed)}/s")
            if job.eta:
                extras.append(tr("job.eta", eta=human_eta(job.eta)))
            if extras:
                text += " · " + " · ".join(extras)
        elif state == JobState.PROCESSING:
            text, kind = tr("job.processing"), "info"
            self.bar.setRange(0, 0)
        elif state == JobState.DONE:
            name = os.path.basename(job.filepath or "")
            text, kind = f"{tr('job.done')} · {name}" if name else tr("job.done"), "ok"
            self.bar.setRange(0, 1000)
            self.bar.setValue(1000)
            bar_state = "done"
        elif state == JobState.CANCELLED:
            text, kind = tr("job.cancelled"), "info"
            self.bar.setRange(0, 1000)
            bar_state = "error"
        else:  # ERROR
            text, kind = error_text(job.error_code), "error"
            self.bar.setRange(0, 1000)
            bar_state = "error"

        self.status.setText(text)
        tooltip = text
        if state == JobState.ERROR and job.error_detail:
            tooltip = f"{text}\n\n{tr('error.details', detail=job.error_detail)}"
        self.status.setToolTip(tooltip)
        _set_kind(self.status, kind)
        if self.bar.property("state") != bar_state:
            self.bar.setProperty("state", bar_state)
            repolish(self.bar)

        self.btn_cancel.setVisible(state in (JobState.WAITING, JobState.RUNNING, JobState.PROCESSING))
        self.btn_retry.setVisible(state in (JobState.ERROR, JobState.CANCELLED))
        self.btn_open.setVisible(state == JobState.DONE)
        self.btn_folder.setVisible(state == JobState.DONE)
        self.btn_remove.setVisible(state not in (JobState.RUNNING, JobState.PROCESSING))
