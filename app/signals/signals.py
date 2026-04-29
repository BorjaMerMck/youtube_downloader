"""
Señales Qt para comunicación entre hilos.
"""
from PySide6.QtCore import QObject, Signal


class Signals(QObject):
    """Señales para comunicación entre el servicio y la UI."""

    log = Signal(str)  # Mensajes de log
    progress = Signal(int)  # 0..100 para descargas
    status = Signal(str)  # Estado actual
    done = Signal(str)  # Trabajo completado
    error = Signal(str)  # Error ocurrido
    cancelled = Signal(str)  # Cancelado por el usuario
    unlock = Signal()  # Desbloquear UI
    busy = Signal(bool)  # Barra indeterminada durante transcripción
    playlist = Signal(list)  # Lista de items (idx, title, id, url)

