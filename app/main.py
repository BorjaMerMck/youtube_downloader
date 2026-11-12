"""
Punto de entrada principal de la aplicación.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

if __package__:
    # Ejecutado como módulo: python -m app.main
    from .ui.ui import MainWindow
else:
    # Ejecutado como script: python app\main.py
    # Añadimos el directorio raíz del proyecto al sys.path para permitir imports absolutos.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.ui.ui import MainWindow


def main() -> None:
    # Identidad propia en la barra de tareas de Windows.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "BorjaMerchanMcKenna.YouTubeDownloader"
        )

    app = QApplication(sys.argv)
    resource_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    icon = QIcon(str(resource_dir / "ico.png"))
    app.setWindowIcon(icon)
    w = MainWindow()
    w.setWindowIcon(icon)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()

