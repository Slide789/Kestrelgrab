"""Dark-Theme (QSS) und zur Laufzeit gezeichnete Grafiken."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

BG = "#0e1014"
SURFACE = "#161922"
SURFACE_2 = "#1d212c"
SURFACE_3 = "#252a37"
BORDER = "#272c39"
BORDER_STRONG = "#353b4b"
TEXT = "#e8eaf0"
MUTED = "#8b92a5"
ACCENT = "#e2692b"
ACCENT_HOVER = "#f07a3a"
ACCENT_PRESSED = "#c95a22"
DANGER = "#ff6372"
SUCCESS = "#3ecf8e"
WARNING = "#f5b74e"


def _asset_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "Kestrelgrab" / "qss"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _draw_chevron(path: Path, color: str, up: bool = False, size: int = 24) -> None:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), size * 0.12)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    s = size
    if up:
        pts = [QPointF(s * 0.25, s * 0.62), QPointF(s * 0.5, s * 0.37), QPointF(s * 0.75, s * 0.62)]
    else:
        pts = [QPointF(s * 0.25, s * 0.38), QPointF(s * 0.5, s * 0.63), QPointF(s * 0.75, s * 0.38)]
    p.drawPolyline(pts)
    p.end()
    img.save(str(path), "PNG")


def generate_arrows() -> dict[str, str]:
    """Zeichnet die Pfeile für Comboboxen/Spinboxen als PNG und liefert die Pfade."""
    d = _asset_dir()
    files = {
        "down": (d / "chevron_down.png", MUTED, False),
        "down_hover": (d / "chevron_down_hover.png", TEXT, False),
        "up": (d / "chevron_up.png", MUTED, True),
        "up_hover": (d / "chevron_up_hover.png", TEXT, True),
        "down_disabled": (d / "chevron_down_disabled.png", BORDER_STRONG, False),
    }
    result: dict[str, str] = {}
    for key, (path, color, up) in files.items():
        try:
            _draw_chevron(path, color, up)
        except Exception:
            pass
        result[key] = str(path).replace(os.sep, "/")
    return result


def build_stylesheet() -> str:
    a = generate_arrows()
    return f"""
* {{
    font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {TEXT};
    outline: none;
}}
QMainWindow, QDialog, #Root {{
    background: {BG};
}}
QToolTip {{
    background: {SURFACE_2};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 8px;
}}

/* ---------- Karten ---------- */
#Card, #JobCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
#JobCard:hover {{
    border-color: {BORDER_STRONG};
}}
#Banner {{
    background: rgba(245, 183, 78, 0.10);
    border: 1px solid rgba(245, 183, 78, 0.45);
    border-radius: 10px;
}}
#Banner QLabel {{
    color: {WARNING};
}}

/* ---------- Texte ---------- */
#AppTitle {{
    font-size: 17pt;
    font-weight: 700;
}}
#Subtitle, #Muted, #Meta, #Footer, #Legal {{
    color: {MUTED};
}}
#Legal {{
    font-size: 8.5pt;
}}
#SectionTitle {{
    font-size: 11.5pt;
    font-weight: 600;
}}
#PreviewTitle {{
    font-size: 12pt;
    font-weight: 600;
}}
#JobTitle {{
    font-weight: 600;
}}
#Status[kind="error"], #JobStatus[kind="error"] {{
    color: {DANGER};
}}
#Status[kind="ok"], #JobStatus[kind="ok"] {{
    color: {SUCCESS};
}}
#Status[kind="info"], #JobStatus[kind="info"] {{
    color: {MUTED};
}}
#EmptyState {{
    color: {MUTED};
    font-size: 10.5pt;
}}
#FieldLabel {{
    color: {MUTED};
    font-size: 9pt;
}}

/* ---------- Eingabefelder ---------- */
QLineEdit {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 12px;
    selection-background-color: {ACCENT};
}}
QLineEdit:hover {{
    border-color: {BORDER_STRONG};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
#UrlInput {{
    font-size: 10.5pt;
    padding: 11px 14px;
}}

/* ---------- Buttons ---------- */
QPushButton {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {SURFACE_3};
    border-color: {BORDER_STRONG};
}}
QPushButton:pressed {{
    background: {BORDER};
}}
QPushButton:disabled {{
    color: {MUTED};
    background: {SURFACE};
}}
QPushButton[variant="primary"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
}}
QPushButton[variant="primary"]:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[variant="primary"]:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton[variant="primary"]:disabled {{
    background: {SURFACE_3};
    border-color: {SURFACE_3};
    color: {MUTED};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
    padding: 6px 10px;
}}
QPushButton[variant="ghost"]:hover {{
    background: {SURFACE_2};
    color: {TEXT};
}}
QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px 9px;
    color: {MUTED};
    font-weight: 600;
    font-size: 9pt;
}}
QToolButton:hover {{
    background: {SURFACE_2};
    border-color: {BORDER};
    color: {TEXT};
}}
QToolButton:pressed {{
    background: {SURFACE_3};
}}
QToolButton[variant="danger"]:hover {{
    color: {DANGER};
}}
QToolButton[variant="accent"] {{
    color: {ACCENT_HOVER};
}}
#CloseButton {{
    font-size: 12pt;
    padding: 0px 8px;
}}

/* ---------- Combobox ---------- */
QComboBox {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 34px 7px 12px;
    min-height: 18px;
}}
QComboBox:hover {{
    border-color: {BORDER_STRONG};
}}
QComboBox:focus, QComboBox:on {{
    border-color: {ACCENT};
}}
QComboBox:disabled {{
    color: {MUTED};
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
}}
QComboBox::down-arrow {{
    image: url("{a['down']}");
    width: 14px;
    height: 14px;
}}
QComboBox::down-arrow:hover, QComboBox::down-arrow:on {{
    image: url("{a['down_hover']}");
}}
QComboBox::down-arrow:disabled {{
    image: url("{a['down_disabled']}");
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_2};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QComboBox QAbstractItemView::item {{
    min-height: 26px;
    padding: 2px 8px;
    border-radius: 6px;
}}

/* ---------- Spinbox ---------- */
QSpinBox {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 6px 28px 6px 12px;
    min-height: 18px;
}}
QSpinBox:focus {{
    border-color: {ACCENT};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 24px;
    border: none;
    background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; margin-top: 3px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; margin-bottom: 3px; }}
QSpinBox::up-arrow {{ image: url("{a['up']}"); width: 12px; height: 12px; }}
QSpinBox::up-arrow:hover {{ image: url("{a['up_hover']}"); }}
QSpinBox::down-arrow {{ image: url("{a['down']}"); width: 12px; height: 12px; }}
QSpinBox::down-arrow:hover {{ image: url("{a['down_hover']}"); }}

/* ---------- Fortschritt ---------- */
QProgressBar {{
    background: {SURFACE_3};
    border: none;
    border-radius: 2px;
    max-height: 4px;
    min-height: 4px;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 2px;
}}
QProgressBar[state="done"]::chunk {{
    background: {SUCCESS};
}}
QProgressBar[state="error"]::chunk {{
    background: {DANGER};
}}

/* ---------- Scrollbereiche ---------- */
QScrollArea, #QueueContainer {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    border-radius: 3px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {MUTED};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0; width: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    border-radius: 3px;
    min-width: 32px;
}}

/* ---------- Dialog ---------- */
QGroupBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 22px;
    padding: 14px 14px 10px 14px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 6px;
    top: 0px;
    padding: 0 4px;
    color: {TEXT};
}}
QGroupBox QLabel {{
    font-weight: 400;
}}
QMessageBox {{
    background: {SURFACE};
}}
QMessageBox QLabel {{
    min-width: 320px;
}}
"""


def rounded_pixmap(source: QPixmap, width: int, height: int, radius: float,
                   device_ratio: float = 1.0) -> QPixmap:
    """Skaliert auf 'cover' und schneidet mit abgerundeten Ecken zu."""
    w, h = int(width * device_ratio), int(height * device_ratio)
    scaled = source.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - w) // 2)
    y = max(0, (scaled.height() - h) // 2)
    scaled = scaled.copy(x, y, w, h)
    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius * device_ratio, radius * device_ratio)
    p.setClipPath(path)
    p.drawPixmap(0, 0, scaled)
    p.end()
    out.setDevicePixelRatio(device_ratio)
    return out


def placeholder_pixmap(width: int, height: int, radius: float, audio: bool = False,
                       device_ratio: float = 1.0) -> QPixmap:
    """Platzhalter-Vorschaubild mit Play- bzw. Notensymbol."""
    w, h = int(width * device_ratio), int(height * device_ratio)
    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius * device_ratio, radius * device_ratio)
    p.fillPath(path, QColor(SURFACE_3))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(MUTED))
    cx, cy, s = w / 2, h / 2, min(w, h) * 0.22
    if audio:
        p.drawEllipse(QPointF(cx - s * 0.35, cy + s * 0.55), s * 0.38, s * 0.3)
        p.drawRect(QRectF(cx - s * 0.08, cy - s * 0.85, s * 0.16, s * 1.4))
        p.drawRect(QRectF(cx - s * 0.08, cy - s * 0.85, s * 0.7, s * 0.2))
    else:
        tri = QPainterPath()
        tri.moveTo(cx - s * 0.45, cy - s * 0.6)
        tri.lineTo(cx + s * 0.65, cy)
        tri.lineTo(cx - s * 0.45, cy + s * 0.6)
        tri.closeSubpath()
        p.drawPath(tri)
    p.end()
    out.setDevicePixelRatio(device_ratio)
    return out


def pixmap_from_bytes(data: bytes | None) -> QPixmap | None:
    if not data:
        return None
    pm = QPixmap()
    if pm.loadFromData(data) and not pm.isNull():
        return pm
    return None


def repolish(widget) -> None:
    """Wendet das Stylesheet nach Änderung einer dynamischen Property neu an."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
