"""
Punto de entrada principal de la aplicación.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__:
    # Ejecutado como módulo: python -m app.main
    from .ui.ui import MainWindow
else:
    # Ejecutado como script: python app\main.py
    # Añadimos el directorio raíz del proyecto al sys.path para permitir imports absolutos.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.ui.ui import MainWindow


def main() -> None:
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()


if __name__ == "__main__":
    main()

