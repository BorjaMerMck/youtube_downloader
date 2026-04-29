"""
Interfaz gráfica de usuario (UI).
"""
import os
import re
import threading
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QProgressBar,
    QMessageBox,
    QTextEdit,
    QFrame,
    QStackedWidget,
)

from yt_dlp.utils import DownloadError

from ..config import WhisperModel
from ..models.models import Job
from ..services.service import CancelledError, MediaService
from ..signals.signals import Signals


# ---------- Ventana de bienvenida (delante) ----------
class WelcomePage(QWidget):
    """Pantalla inicial: título, créditos y botón para ir al descargador."""

    go_to_app = Signal()

    def __init__(self, on_start=None):
        super().__init__()
        self.setObjectName("WelcomePage")
        self._on_start = on_start
        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 50, 40, 40)
        layout.setSpacing(24)

        self.lbl_app_title = QLabel("YouTube Downloader")
        self.lbl_app_title.setObjectName("WelcomeTitle")

        self.lbl_credits = QLabel("by Borja Merchan McKenna")
        self.lbl_credits.setObjectName("WelcomeCredits")

        layout.addStretch(1)
        layout.addWidget(self.lbl_app_title, 0, Qt.AlignCenter)
        layout.addWidget(self.lbl_credits, 0, Qt.AlignCenter)
        layout.addStretch(1)

        self.btn_start = QPushButton("Comenzar")
        self.btn_start.setObjectName("WelcomeBtn")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._go)
        layout.addWidget(self.btn_start, 0, Qt.AlignCenter)
        layout.addStretch(1)

    def _go(self):
        if self._on_start:
            self._on_start()
        self.go_to_app.emit()

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QWidget#WelcomePage {
                background: #0f1115;
            }
            #WelcomeTitle {
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 0.5px;
                color: #e7e9ee;
            }
            #WelcomeCredits {
                font-size: 14px;
                color: #8b92a3;
                letter-spacing: 0.8px;
            }
            QPushButton#WelcomeBtn {
                background: #3a7afe;
                border: none;
                border-radius: 14px;
                padding: 14px 32px;
                font-size: 15px;
                font-weight: 700;
                color: #fff;
            }
            QPushButton#WelcomeBtn:hover {
                background: #2f6cf0;
            }
        """
        )


# ---------- Contenedor con menú switch (bienvenida <-> descargador) ----------
class MainWindow(QWidget):
    """Ventana principal: stacked widget para cambiar entre bienvenida y descargador."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader + Transcripción")
        self.resize(920, 560)
        self.setStyleSheet("QWidget#MainWindow { background: #0f1115; }")
        self.setObjectName("MainWindow")
        self._init_ui()

    def _init_ui(self):
        self.stack = QStackedWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self.welcome = WelcomePage()
        self.welcome.go_to_app.connect(self._show_downloader)
        self.stack.addWidget(self.welcome)

        self.downloader = App(on_show_menu=self._show_welcome)
        self.stack.addWidget(self.downloader)

        self.stack.setCurrentIndex(0)

    def _show_welcome(self):
        self.stack.setCurrentIndex(0)

    def _show_downloader(self):
        self.stack.setCurrentIndex(1)


class App(QWidget):
    """Pantalla del descargador (vídeo/audio/transcripción)."""

    def __init__(self, on_show_menu=None):
        super().__init__()
        self._on_show_menu = on_show_menu

        self.signals = Signals()
        self.signals.log.connect(self._log)
        self.signals.progress.connect(self._set_progress)
        self.signals.status.connect(self._set_status)
        self.signals.done.connect(self._done)
        self.signals.error.connect(self._error)
        self.signals.cancelled.connect(self._cancelled)
        self.signals.unlock.connect(self._unlock)
        self.signals.busy.connect(self._set_busy)
        self.signals.playlist.connect(self._show_playlist_items)

        self.service = MediaService(self.signals)

        self._log_messages: list[str] = []
        self._max_log_lines = 300
        self._last_outputs: list[str] = []
        self._last_out_dir: str = ""

        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        """Inicializa todos los componentes de la UI."""
        # ---- Header (título + botón Menú) ----
        header = QHBoxLayout()
        header.setSpacing(12)
        self.lbl_title = QLabel("YouTube Downloader")
        self.lbl_title.setObjectName("Title")
        header.addWidget(self.lbl_title)
        header.addStretch(1)
        if self._on_show_menu:
            self.btn_menu = QPushButton("Menú")
            self.btn_menu.setObjectName("MenuBtn")
            self.btn_menu.setCursor(Qt.PointingHandCursor)
            self.btn_menu.clicked.connect(self._on_show_menu)
            header.addWidget(self.btn_menu)

        self.lbl_subtitle = QLabel("Descarga MP4/MP3 y transcribe a TXT desde una URL.")
        self.lbl_subtitle.setObjectName("Subtitle")

        # ---- Inputs ----
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Pega la URL de YouTube…")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setObjectName("UrlInput")

        self.btn_playlist = QPushButton("Ver playlist")
        self.btn_playlist.setObjectName("SecondaryBtn")
        self.btn_playlist.clicked.connect(self.show_playlist)

        self.out_dir = self._get_default_videos_dir()
        self.out_label = QLabel(self.out_dir)
        self.out_label.setObjectName("MutedLabel")

        self.btn_dir = QPushButton("Elegir carpeta…")
        self.btn_dir.clicked.connect(self.choose_dir)
        self.btn_dir.setObjectName("SecondaryBtn")

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.clicked.connect(self.clear_ui)
        self.btn_clear.setObjectName("SecondaryBtn")

        self.chk_video = QCheckBox("Vídeo (MP4)")
        self.chk_video.setChecked(True)

        self.chk_audio = QCheckBox("Audio (MP3)")
        self.chk_audio.setChecked(True)

        self.chk_transcribe = QCheckBox("Transcribir (TXT)")
        self.chk_transcribe.setChecked(False)

        self.btn_run = QPushButton("Ejecutar")
        self.btn_run.clicked.connect(self.run)
        self.btn_run.setObjectName("PrimaryBtn")

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.cancel)
        self.btn_cancel.setObjectName("SecondaryBtn")
        self.btn_cancel.setEnabled(False)

        self.btn_open_folder = QPushButton("Abrir carpeta")
        self.btn_open_folder.clicked.connect(self.open_out_dir)
        self.btn_open_folder.setObjectName("SecondaryBtn")
        self.btn_open_folder.setEnabled(False)

        # ---- Progress / status ----
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.status_label = QLabel("Estado: listo")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setWordWrap(True)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setObjectName("LogBox")

        # ---- Card layout (grid tipo formulario: etiqueta | contenido) ----
        card = QFrame()
        card.setObjectName("Card")
        card.setFrameShape(QFrame.StyledPanel)

        grid = QGridLayout(card)
        grid.setContentsMargins(24, 22, 24, 22)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(1, 1)  # la columna de contenido ocupa el espacio sobrante
        grid.setColumnMinimumWidth(0, 72)  # etiquetas alineadas

        # Fila 0: URL
        lbl_url = QLabel("URL")
        lbl_url.setObjectName("GridLabel")
        grid.addWidget(lbl_url, 0, 0, Qt.AlignLeft | Qt.AlignTop)
        row_url = QHBoxLayout()
        row_url.setSpacing(10)
        row_url.addWidget(self.url_input, 1)
        row_url.addWidget(self.btn_playlist)
        grid.addLayout(row_url, 0, 1, 1, 1)

        # Fila 1: Carpeta (ruta + botones en la misma línea)
        lbl_carpeta = QLabel("Carpeta")
        lbl_carpeta.setObjectName("GridLabel")
        grid.addWidget(lbl_carpeta, 1, 0, Qt.AlignLeft | Qt.AlignTop)
        row_dir = QHBoxLayout()
        row_dir.setSpacing(10)
        row_dir.addWidget(self.out_label, 1)
        row_dir.addWidget(self.btn_dir)
        row_dir.addWidget(self.btn_clear)
        grid.addLayout(row_dir, 1, 1, 1, 1)

        # Fila 2: Opciones (vídeo, audio, transcribir)
        lbl_opts = QLabel("Opciones")
        lbl_opts.setObjectName("GridLabel")
        grid.addWidget(lbl_opts, 2, 0, Qt.AlignLeft | Qt.AlignTop)
        row_opts = QHBoxLayout()
        row_opts.setSpacing(20)
        row_opts.addWidget(self.chk_video)
        row_opts.addWidget(self.chk_audio)
        row_opts.addWidget(self.chk_transcribe)
        row_opts.addStretch(1)
        grid.addLayout(row_opts, 2, 1, 1, 1)

        # Fila 3: Acción principal
        row_actions = QHBoxLayout()
        row_actions.setSpacing(12)
        row_actions.addWidget(self.btn_run)
        row_actions.addWidget(self.btn_cancel)
        row_actions.addWidget(self.btn_open_folder)
        row_actions.addStretch(1)
        grid.addLayout(row_actions, 3, 0, 1, 2)

        # ---- Root layout ----
        root = QVBoxLayout()
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        root.addLayout(header)
        root.addWidget(self.lbl_subtitle)
        root.addWidget(card)

        root.addWidget(self.progress)
        root.addWidget(self.status_label)

        lbl_log = QLabel("Log")
        lbl_log.setObjectName("SectionTitle")
        root.addWidget(lbl_log)
        root.addWidget(self.log_box, 1)

        self.setLayout(root)

    # ---------- Styling ----------
    def _apply_styles(self):
        """Aplica estilos CSS a la interfaz."""
        f = QFont()
        f.setPointSize(10)
        self.setFont(f)

        self.setStyleSheet(
            """
            QWidget {
                background: #0f1115;
                color: #e7e9ee;
            }
            #Title {
                font-size: 26px;
                font-weight: 800;
                letter-spacing: 0.2px;
            }
            #Subtitle {
                color: #a9afbd;
                margin-bottom: 2px;
            }
            #Card {
                background: #151924;
                border: 1px solid #23293a;
                border-radius: 16px;
            }
            QLabel { font-size: 12px; }
            #MutedLabel { color: #a9afbd; }
            #GridLabel {
                color: #8b92a3;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.3px;
                padding-top: 2px;
            }
            #SectionTitle { font-size: 12px; font-weight: 700; color: #cfd3dd; }
            #StatusLabel { color: #c7cbd6; }

            QLineEdit#UrlInput {
                background: #0f1115;
                border: 1px solid #2a3145;
                border-radius: 12px;
                padding: 10px 12px;
                font-size: 13px;
            }
            QLineEdit#UrlInput:focus { border: 1px solid #3a7afe; }

            QCheckBox { spacing: 8px; color: #d9dbe2; }
            QCheckBox::indicator { width: 18px; height: 18px; }

            QTextEdit#LogBox {
                background: #0f1115;
                border: 1px solid #23293a;
                border-radius: 14px;
                padding: 10px;
                color: #dfe3ee;
            }

            QProgressBar {
                background: #151924;
                border: 1px solid #23293a;
                border-radius: 10px;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background: #3a7afe;
                border-radius: 10px;
            }

            QPushButton#PrimaryBtn {
                background: #3a7afe;
                border: none;
                border-radius: 12px;
                padding: 10px 16px;
                font-weight: 800;
            }
            QPushButton#PrimaryBtn:hover { background: #2f6cf0; }
            QPushButton#PrimaryBtn:disabled { background: #2a3145; color: #7c8496; }

            QPushButton#SecondaryBtn {
                background: #1b2030;
                border: 1px solid #2a3145;
                border-radius: 12px;
                padding: 10px 14px;
                color: #e7e9ee;
            }
            QPushButton#SecondaryBtn:hover { background: #212840; }
            QPushButton#SecondaryBtn:disabled { color: #7c8496; border-color: #23293a; }

            QPushButton#MenuBtn {
                background: transparent;
                border: 1px solid #2a3145;
                border-radius: 10px;
                padding: 8px 14px;
                color: #a9afbd;
                font-size: 12px;
            }
            QPushButton#MenuBtn:hover { background: #1b2030; color: #e7e9ee; }
        """
        )

    # ---------- UI helpers ----------
    def _log(self, msg: str):
        """Agrega un mensaje al log."""
        self._log_messages.append(msg)
        if len(self._log_messages) > self._max_log_lines:
            self._log_messages = self._log_messages[-self._max_log_lines :]
        self.log_box.setPlainText("\n".join(self._log_messages))
        # Mantener el scroll al final para ver lo último.
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def _set_progress(self, val: int):
        """Actualiza la barra de progreso."""
        self.progress.setValue(val)

    def _set_status(self, msg: str):
        """Actualiza el estado."""
        self.status_label.setText(f"Estado: {msg}")

    def _set_busy(self, is_busy: bool):
        """Cambia entre barra determinada e indeterminada."""
        if is_busy:
            self.progress.setRange(0, 0)  # indeterminado
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

    def clear_ui(self):
        """Limpia la interfaz."""
        self.log_box.clear()
        self._log_messages.clear()
        self.btn_open_folder.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_status("listo")

    def _show_playlist_items(self, items: list):
        """Muestra en el log los items de una playlist."""
        self._log(f"Playlist detectada: {len(items)} elementos")
        for it in items:
            try:
                idx = it.get("idx")
                title = it.get("title")
                self._log(f"{idx:>3}. {title}")
            except Exception:
                continue
        self._set_status("playlist lista")

    def _lock(self):
        """Bloquea los controles durante una operación."""
        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_open_folder.setEnabled(False)
        self.btn_dir.setEnabled(False)
        self.btn_clear.setEnabled(False)
        self.chk_video.setEnabled(False)
        self.chk_audio.setEnabled(False)
        self.chk_transcribe.setEnabled(False)

    def _unlock(self):
        """Desbloquea los controles."""
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_dir.setEnabled(True)
        self.btn_clear.setEnabled(True)
        self.chk_video.setEnabled(True)
        self.chk_audio.setEnabled(True)
        self.chk_transcribe.setEnabled(True)

    def _done(self, msg: str):
        """Muestra mensaje de éxito."""
        self.btn_open_folder.setEnabled(True)
        self._set_status("listo")
        QMessageBox.information(self, "OK", msg)

    def _error(self, msg: str):
        """Muestra mensaje de error."""
        self.btn_open_folder.setEnabled(False)
        QMessageBox.critical(self, "Error", msg)

    def _cancelled(self, msg: str):
        """Muestra mensaje cuando el usuario cancela el trabajo."""
        self.btn_open_folder.setEnabled(False)
        self._set_status("cancelado")
        QMessageBox.information(self, "Cancelado", msg)

    # ---------- actions ----------
    def choose_dir(self):
        """Abre diálogo para elegir carpeta de salida."""
        folder = QFileDialog.getExistingDirectory(self, "Selecciona carpeta de salida")
        if folder:
            self.out_dir = folder
            self.out_label.setText(folder)

    def _normalize_youtube_url(self, url: str) -> str | None:
        """Valida y normaliza URLs típicas de YouTube."""
        raw = (url or "").strip()
        if not raw:
            return None

        # Permite pegar sin esquema.
        if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
            raw = "https://" + raw

        try:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
            if host in {"youtu.be", "www.youtu.be"}:
                video_id = parsed.path.lstrip("/").split("/")[0]
                return f"https://youtu.be/{video_id}" if video_id else None

            if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
                qs = parse_qs(parsed.query)
                video_id = qs.get("v", [None])[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"

                # Solo tratar como playlist cuando NO hay vídeo.
                playlist_id = qs.get("list", [None])[0]
                if playlist_id:
                    return f"https://www.youtube.com/playlist?list={playlist_id}"

                parts = [p for p in parsed.path.split("/") if p]
                # /shorts/<id>, /embed/<id>, /live/<id>
                if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
                    video_id = parts[1]
                    return f"https://www.youtube.com/watch?v={video_id}"

            return None
        except Exception:
            return None

    def _extract_playlist_url(self, url: str) -> str | None:
        """Intenta extraer una URL de playlist a partir de cualquier URL de YouTube.

        Soporta casos típicos:
        - https://www.youtube.com/playlist?list=...
        - https://www.youtube.com/watch?v=...&list=...
        - https://music.youtube.com/watch?v=...&list=...
        """
        raw = (url or "").strip()
        if not raw:
            return None
        if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
            raw = "https://" + raw
        try:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
            if not (host.endswith("youtube.com") or host.endswith("youtube-nocookie.com")):
                return None
            qs = parse_qs(parsed.query)
            list_id = (qs.get("list") or [None])[0]
            if list_id:
                return f"https://www.youtube.com/playlist?list={list_id}"
            if parsed.path.startswith("/playlist"):
                return raw
            return None
        except Exception:
            return None

    def open_out_dir(self):
        """Abre la carpeta de salida del último trabajo completado."""
        if not self._last_out_dir:
            QMessageBox.warning(self, "Carpeta", "No hay una carpeta para abrir todavía.")
            return
        if not os.path.isdir(self._last_out_dir):
            QMessageBox.warning(self, "Carpeta", "La carpeta de salida ya no existe.")
            return
        os.startfile(self._last_out_dir)  # type: ignore[attr-defined]

    def _get_default_videos_dir(self) -> str:
        """Devuelve la carpeta de Videos del usuario (creándola si hace falta)."""
        base = os.path.join(os.path.expanduser("~"), "Videos")
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            # Fallback: usa el directorio del usuario si Videos no se puede crear.
            base = os.path.expanduser("~")
        return base

    def cancel(self):
        """Solicita cancelar el trabajo actual."""
        if not self.service or not hasattr(self.service, "request_cancel"):
            return
        self.btn_cancel.setEnabled(False)
        self.btn_open_folder.setEnabled(False)
        self._set_status("cancelando…")
        self.signals.log.emit("Cancelando…")
        self.service.request_cancel()

    def show_playlist(self):
        """Lee una playlist y muestra sus títulos en el log."""
        url_raw = self.url_input.text().strip()
        playlist_url = self._extract_playlist_url(url_raw)
        if not playlist_url:
            # Fallback: si no se pudo extraer playlist, al menos validar que sea YouTube.
            if not self._normalize_youtube_url(url_raw):
                QMessageBox.warning(self, "URL no válida", "Introduce una URL de YouTube válida.")
            else:
                QMessageBox.information(
                    self,
                    "No es playlist",
                    "No he encontrado parámetro 'list=' en la URL. "
                    "Pega un enlace de playlist o uno de vídeo que incluya &list=...",
                )
            return

        self.log_box.clear()
        self._log_messages.clear()
        self._set_status("leyendo playlist…")
        self._lock()

        t = threading.Thread(target=self._playlist_worker, args=(playlist_url,), daemon=True)
        t.start()

    def run(self):
        """Inicia el proceso de descarga/transcripción."""
        job = self._build_job_or_show_error()
        if not job:
            return

        self._last_outputs = []
        self._last_out_dir = job.out_dir
        self.btn_open_folder.setEnabled(False)
        self.log_box.clear()
        self._log_messages.clear()
        self._set_status("iniciando…")
        self._lock()

        t = threading.Thread(target=self._worker, args=(job,), daemon=True)
        t.start()

    # ---------- job helpers ----------
    def _build_job_or_show_error(self) -> Job | None:
        """Construye un Job validando los datos de entrada."""
        url_raw = self.url_input.text().strip()
        if not url_raw:
            QMessageBox.warning(self, "Falta URL", "Introduce una URL.")
            return None

        url = self._normalize_youtube_url(url_raw)
        if not url:
            QMessageBox.warning(
                self,
                "URL no válida",
                "Parece que no es una URL de YouTube. Revisa el formato (ej. watch?v=... o youtu.be/...).",
            )
            return None

        if not self.out_dir:
            QMessageBox.warning(self, "Falta carpeta", "Elige una carpeta de salida.")
            return None

        do_video = self.chk_video.isChecked()
        do_audio = self.chk_audio.isChecked()
        do_transcribe = self.chk_transcribe.isChecked()

        if not do_video and not do_audio and not do_transcribe:
            QMessageBox.warning(self, "Nada seleccionado", "Selecciona al menos una opción.")
            return None

        # Si el usuario pegó un link de vídeo con parámetro list=, dejar elegir
        # entre descargar solo el vídeo (normalizado) o toda la playlist.
        playlist_url = self._extract_playlist_url(url_raw)
        if playlist_url and (do_video or do_audio):
            reply = QMessageBox.question(
                self,
                "Descargar playlist",
                "Esta URL contiene una playlist.\n\n"
                "¿Quieres descargar TODA la playlist (en vez de solo el vídeo)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                url = playlist_url
                if do_transcribe:
                    QMessageBox.information(
                        self,
                        "Transcripción en playlists",
                        "La transcripción (TXT) para playlists todavía no está soportada.\n"
                        "Voy a desactivar 'Transcribir (TXT)' y descargar solo vídeo/audio.",
                    )
                    self.chk_transcribe.setChecked(False)
                    do_transcribe = False

        if do_transcribe and "youtube.com/playlist" in url:
            QMessageBox.warning(
                self,
                "Transcripción en playlists",
                "La transcripción para playlists todavía no está soportada. "
                "Desmarco 'Transcribir (TXT)'.",
            )
            self.chk_transcribe.setChecked(False)
            do_transcribe = False

        # Evitar trabajo duplicado si solo quieres vídeo y también MP3 (sin transcripción).
        if do_video and do_audio and not do_transcribe:
            reply = QMessageBox.question(
                self,
                "Evitar duplicado de audio",
                "Ya descargarás el vídeo con audio (MP4). ¿Quieres también generar el MP3?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                do_audio = False
                self.chk_audio.setChecked(False)

        if do_transcribe and WhisperModel is None:
            QMessageBox.warning(
                self,
                "faster-whisper no disponible",
                "No se pudo importar faster-whisper.\nInstala con: python -m pip install -U faster-whisper",
            )
            return None

        return Job(url=url, out_dir=self.out_dir, do_video=do_video, do_audio=do_audio, do_transcribe=do_transcribe)

    def _worker(self, job: Job):
        """Worker que ejecuta el trabajo en un hilo separado."""
        try:
            outputs = self.service.run_job(job)
            self._last_outputs = outputs
            # Guardar la carpeta del vídeo (la del primer archivo existente).
            last_dir = ""
            for o in outputs:
                if ":" not in o:
                    continue
                _, maybe_path = o.split(":", 1)
                maybe_path = maybe_path.strip()
                if maybe_path and os.path.exists(maybe_path):
                    if os.path.isdir(maybe_path):
                        last_dir = maybe_path
                    else:
                        last_dir = os.path.dirname(maybe_path)
                    break
            self._last_out_dir = last_dir or job.out_dir
            self.signals.status.emit("listo")
            self.signals.done.emit("Completado:\n\n" + "\n".join(outputs))
        except DownloadError as e:
            if self.service.is_cancelled():
                self.signals.cancelled.emit("Cancelado por el usuario.")
            else:
                self.signals.error.emit(
                    "Error de descarga (yt-dlp).\n\n"
                    f"{e}\n\n"
                    "Si menciona ffmpeg/ffprobe: revisa FFMPEG_DIR.\n"
                    "Si es timeout: reintenta o sube socket_timeout."
                )
        except CancelledError:
            self.signals.cancelled.emit("Cancelado por el usuario.")
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.busy.emit(False)
            self.signals.unlock.emit()

    def _playlist_worker(self, url: str):
        """Worker para listar elementos de una playlist."""
        try:
            items = self.service.fetch_playlist_items(url)
            self.signals.playlist.emit(items)
        except CancelledError:
            self.signals.cancelled.emit("Cancelado por el usuario.")
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.busy.emit(False)
            self.signals.unlock.emit()

