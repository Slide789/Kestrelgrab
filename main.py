"""Einstiegspunkt von Kestrelgrab."""

from __future__ import annotations

import os
import sys


def _set_app_user_model_id() -> None:
    """Eigene Taskleisten-Gruppe und eigenes Icon unter Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes

        from app import APP_ID

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _load_icon():
    from PySide6.QtGui import QIcon

    from app.core import resource_dir

    assets = resource_dir() / "assets"
    icon = QIcon()
    for name in ("icon.ico", "icon.png"):
        path = assets / name
        if path.is_file():
            icon.addFile(str(path))
    return icon


def main() -> int:
    _set_app_user_model_id()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from app import APP_NAME, APP_VERSION, i18n
    from app.settings import Settings
    from app.ui.main_window import MainWindow
    from app.ui.style import build_stylesheet

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    icon = _load_icon()
    app.setWindowIcon(icon)

    settings = Settings()
    i18n.set_language(settings.language)

    window = MainWindow(settings, icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
