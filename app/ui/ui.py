"""
Interfaz gráfica de usuario (UI).
"""
import os
import re
import threading
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QScrollArea,
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
    QDialog,
    QComboBox,
    QDialogButtonBox,
)

from yt_dlp.utils import DownloadError

from ..config import WhisperModel
from ..models.models import Job
from ..services.service import CancelledError, MediaService
from ..signals.signals import Signals


# ---------- Ventana de bienvenida (delante) ----------
class WelcomePage(QWidget):
    """Pantalla inicial con tabla de funciones, créditos y acceso al descargador."""

    go_to_app = Signal()

    def __init__(self, on_start=None):
        super().__init__()
        self.setObjectName("WelcomePage")
        self._on_start = on_start
        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("WelcomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("WelcomeBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(28, 32, 28, 32)
        layout.setSpacing(18)
        layout.addStretch(1)

        self.lbl_app_title = QLabel("YouTube Downloader")
        self.lbl_app_title.setObjectName("WelcomeTitle")
        self.lbl_app_title.setWordWrap(True)
        self.lbl_app_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_app_title)
        subtitle = QLabel("Descarga vídeos, extrae audio y convierte voz en texto")
        subtitle.setObjectName("WelcomeSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        table = QFrame()
        table.setObjectName("FeaturesTable")
        table.setMaximumWidth(760)
        grid = QGridLayout(table)
        grid.setContentsMargins(22, 18, 22, 18)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(13)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)
        for column, text in enumerate(("FUNCIÓN", "QUÉ PUEDES HACER")):
            label = QLabel(text)
            label.setObjectName("FeatureHeader")
            grid.addWidget(label, 0, column)
        rows = (
            ("Vídeo · MP4", "Descarga vídeos con audio y selecciona la calidad."),
            ("Audio · MP3", "Extrae el audio y guárdalo en formato MP3."),
            ("Transcripción · TXT", "Convierte el audio en un archivo de texto."),
            ("Playlists", "Procesa los vídeos de una lista consecutivamente."),
            ("Opciones combinadas", "Elige vídeo, audio y transcripción en una misma ejecución."),
        )
        for index, (name, description) in enumerate(rows):
            separator = QFrame()
            separator.setObjectName("FeatureSeparator")
            separator.setFixedHeight(1)
            grid.addWidget(separator, index * 2 + 1, 0, 1, 2)
            title = QLabel(name)
            title.setObjectName("FeatureName")
            title.setWordWrap(True)
            detail = QLabel(description)
            detail.setObjectName("FeatureDetail")
            detail.setWordWrap(True)
            grid.addWidget(title, index * 2 + 2, 0)
            grid.addWidget(detail, index * 2 + 2, 1)
        table_row = QHBoxLayout()
        table_row.addStretch(1)
        table_row.addWidget(table, 10)
        table_row.addStretch(1)
        layout.addLayout(table_row)

        self.btn_start = QPushButton("Comenzar")
        self.btn_start.setObjectName("WelcomeBtn")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._go)
        layout.addWidget(self.btn_start, 0, Qt.AlignCenter)

        self.lbl_credits = QLabel("by Borja Merchan McKenna")
        self.lbl_credits.setObjectName("WelcomeCredits")
        layout.addWidget(self.lbl_credits, 0, Qt.AlignCenter)
        self.lbl_profiles = QLabel(
            '<a href="https://www.linkedin.com/in/borja-merchan-mckenna/" '
            'style="color: #8eb7ff;">LinkedIn</a>'
            ' &nbsp; · &nbsp; '
            '<a href="https://github.com/BorjaMerMck" '
            'style="color: #8eb7ff;">GitHub</a>'
        )
        self.lbl_profiles.setObjectName("WelcomeProfiles")
        self.lbl_profiles.setTextFormat(Qt.RichText)
        self.lbl_profiles.setTextInteractionFlags(
            Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard
        )
        self.lbl_profiles.setOpenExternalLinks(True)
        self.lbl_profiles.setAccessibleName("Perfiles de Borja: LinkedIn y GitHub")
        layout.addWidget(self.lbl_profiles, 0, Qt.AlignCenter)
        layout.addStretch(1)

    def _go(self):
        if self._on_start:
            self._on_start()
        self.go_to_app.emit()

    def _apply_styles(self):
        self.setStyleSheet(
            """
            #WelcomeScroll, #WelcomeBody { background: #0f1115; border: none; }
            #WelcomeSubtitle { color: #a6afbf; font-size: 15px; }
            QFrame#FeaturesTable {
                background: #171c26;
                border: 1px solid #2b3548;
                border-radius: 16px;
            }
            #FeatureHeader { color: #8eb7ff; font-size: 11px; font-weight: 700; }
            #FeatureName { color: #edf1f8; font-size: 14px; font-weight: 600; }
            #FeatureDetail { color: #b3bdcf; font-size: 14px; }
            #FeatureSeparator { background: #2b3548; border: none; }
            QPushButton#WelcomeBtn:focus { border: 2px solid #b8d0ff; }
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
            #WelcomeProfiles {
                font-size: 14px;
                color: #8b92a3;
                padding: 4px;
            }
        """
        )


# ---------- Contenedor con menú switch (bienvenida <-> descargador) ----------
class MainWindow(QWidget):
    """Ventana principal: stacked widget para cambiar entre bienvenida y descargador."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader + Transcripción")
        self.resize(980, 760)
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


def _fmt_duration(seconds) -> str | None:
    if not seconds:
        return None
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class QualityConfirmDialog(QDialog):
    """Avisa la mejor calidad disponible y deja confirmar u elegir otra."""

    def __init__(self, parent: QWidget, info: dict):
        super().__init__(parent)
        self.setWindowTitle("Calidad del vídeo")
        self.setModal(True)
        self.resize(460, 220)

        best = info.get("best_height")
        fps = info.get("best_fps")
        vcodec = (info.get("best_vcodec") or "").split(".")[0]
        title = info.get("title") or "(sin título)"
        duration = _fmt_duration(info.get("duration"))

        lines = []
        if info.get("is_playlist"):
            plist = info.get("playlist_title") or "Playlist"
            count = info.get("count") or 0
            lines.append(f"Playlist: {plist}")
            lines.append(f"Vídeos: {count}")
            lines.append("")
            lines.append(f"Primer vídeo: {title}")
        else:
            lines.append(f"Título: {title}")
        if duration:
            lines.append(f"Duración: {duration}")
        lines.append("")
        if best:
            extra = []
            if fps:
                extra.append(f"{int(fps)} fps")
            if vcodec and vcodec != "none":
                extra.append(vcodec)
            suffix = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"La mejor calidad disponible es {best}p{suffix}.")
        else:
            lines.append("No se pudo listar resoluciones; se intentará la máxima calidad.")
        if info.get("is_playlist"):
            lines.append("Esa calidad se usará como tope para toda la playlist.")
        lines.append("¿Quieres descargar, o eliges otra calidad?")

        layout = QVBoxLayout(self)
        lbl = QLabel("\n".join(lines))
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.combo = QComboBox()
        best_label = f"{best}p" if best else "máxima"
        self.combo.addItem(f"Máxima disponible ({best_label})", None)
        for height in info.get("heights") or []:
            meta = (info.get("by_height") or {}).get(height) or {}
            h_fps = meta.get("fps")
            label = f"{height}p"
            if h_fps:
                label += f"  {int(h_fps)} fps"
            if height == best:
                label += "  — mejor"
            self.combo.addItem(label, height)
        layout.addWidget(self.combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Descargar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_height(self) -> int | None:
        data = self.combo.currentData()
        return int(data) if data else None


class OutputCard(QFrame):
    """Tarjeta multiselección; la casilla conserva acceso por teclado."""

    def __init__(self, title: str, description: str, checked=False):
        super().__init__()
        self.setObjectName("OutputCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(165)
        self.setMinimumHeight(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        self.checkbox = QCheckBox(title)
        self.checkbox.setAccessibleDescription(description)
        self.checkbox.setCursor(Qt.PointingHandCursor)
        self.description = QLabel(description)
        self.description.setObjectName("CardDescription")
        self.description.setWordWrap(True)
        self.description.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.description)
        layout.addStretch()
        self.checkbox.toggled.connect(self._refresh)
        self.checkbox.setChecked(checked)
        self._refresh(checked)

    def isChecked(self):
        return self.checkbox.isChecked()

    def setChecked(self, checked):
        self.checkbox.setChecked(checked)

    def _refresh(self, checked):
        self.setProperty("selected", checked)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.LeftButton and self.isEnabled()
                and self.rect().contains(event.position().toPoint())):
            self.checkbox.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)


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
        self.signals.quality_ready.connect(self._on_quality_ready)
        self.signals.stages.connect(self._set_stages)

        self.service = MediaService(self.signals)

        self._log_messages: list[str] = []
        self._max_log_lines = 300
        self._last_outputs: list[str] = []
        self._last_out_dir: str = ""
        self._operation_active = False

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

        self.chk_video = OutputCard("Vídeo · MP4", "Vídeo con audio y selección de calidad.", True)
        self.chk_audio = OutputCard("Audio · MP3", "Audio independiente para escuchar.", True)
        self.chk_transcribe = OutputCard("Texto · TXT", "Transcripción en español. Incluye MP3.")

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
        self.progress.setFormat("Transferencia actual: %p%")

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
        row_opts.addWidget(self.chk_video, 1)
        row_opts.addWidget(self.chk_audio, 1)
        row_opts.addWidget(self.chk_transcribe, 1)
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

        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 16, 18, 16)
        self.phase_label = QLabel("Preparado para comenzar")
        self.phase_label.setObjectName("PhaseLabel")
        self.phase_label.setWordWrap(True)
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 1)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("Sin trabajo iniciado")
        hint = QLabel("Avance por etapas; no representa el tiempo restante.")
        hint.setObjectName("MutedLabel")
        hint.setWordWrap(True)
        status_layout.addWidget(self.phase_label)
        status_layout.addWidget(self.overall_progress)
        status_layout.addWidget(hint)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress)
        root.addWidget(status_card)

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

        self.setStyleSheet(self.styleSheet() + """
            QFrame#OutputCard {
                background: #171d29; border: 2px solid #303b50; border-radius: 12px;
            }
            QFrame#OutputCard:hover { border-color: #7a9ce6; }
            QFrame#OutputCard[selected="true"] {
                background: #1c3052; border-color: #669bff;
            }
            QFrame#OutputCard:disabled { border-color: #303b50; }
            QFrame#OutputCard QCheckBox {
                background: transparent; font-size: 15px; font-weight: 600;
            }
            QFrame#OutputCard QCheckBox:focus { color: #99bfff; }
            QFrame#OutputCard QLabel { background: transparent; }
            QLabel#CardDescription { color: #b4bfd2; font-size: 12px; }
            QFrame#StatusCard {
                background: #151b26; border: 1px solid #303b50; border-radius: 12px;
            }
            QFrame#StatusCard QLabel { background: transparent; }
            QLabel#PhaseLabel { color: #e7efff; font-size: 16px; font-weight: 600; }
        """)

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
        """Actividad sin porcentaje cuando no se conoce el avance real."""
        if is_busy:
            self.progress.setRange(0, 0)
        elif self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

    def _reset_tracking(self, label="Preparado para comenzar"):
        self.phase_label.setText(label)
        self.overall_progress.setRange(0, 1)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("Sin etapas completadas")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _set_stages(self, completed: int, total: int, label: str):
        self.overall_progress.setRange(0, max(1, total))
        self.overall_progress.setValue(completed)
        self.overall_progress.setFormat(f"{completed} de {total} etapas completadas")
        if label:
            self.phase_label.setText(f"Paso {completed + 1} de {total}: {label}")
        elif completed == total:
            self.phase_label.setText("Todas las etapas completadas")

    def clear_ui(self):
        """Limpia la interfaz."""
        self._reset_tracking()
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
        self.phase_label.setText("Consulta de playlist completada")

    def _lock(self):
        """Bloquea los controles durante una operación."""
        self._operation_active = True
        self.btn_playlist.setEnabled(False)
        self.url_input.setEnabled(False)
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
        self._operation_active = False
        self.btn_playlist.setEnabled(True)
        self.url_input.setEnabled(True)
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
        self._set_busy(False)
        self.progress.setValue(100)
        self._set_status("completado")
        self.phase_label.setText("Trabajo completado")
        QMessageBox.information(self, "OK", msg)

    def _error(self, msg: str):
        """Muestra mensaje de error."""
        self.btn_open_folder.setEnabled(False)
        self._set_busy(False)
        self._set_status("error")
        self.phase_label.setText("Operación interrumpida por un error")
        QMessageBox.critical(self, "Error", msg)

    def _cancelled(self, msg: str):
        """Muestra mensaje cuando el usuario cancela el trabajo."""
        self.btn_open_folder.setEnabled(False)
        self._set_busy(False)
        self.phase_label.setText("Operación cancelada")
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
        self.phase_label.setText("Cancelando; esperando a que termine la operación actual…")
        self._set_status("cancelando…")
        self.signals.log.emit("Cancelando…")
        self.service.request_cancel()

    def show_playlist(self):
        """Lee una playlist y muestra sus títulos en el log."""
        if self._operation_active:
            return
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
        self._reset_tracking("Consultando playlist")
        self._set_status("leyendo playlist…")
        self._lock()

        t = threading.Thread(target=self._playlist_worker, args=(playlist_url,), daemon=True)
        t.start()

    def run(self):
        """Inicia el proceso de descarga/transcripción."""
        if self._operation_active:
            return
        job = self._build_job_or_show_error()
        if not job:
            return

        self._reset_tracking("Preparando trabajo")
        self._last_outputs = []
        self._last_out_dir = job.out_dir
        self.btn_open_folder.setEnabled(False)
        self.log_box.clear()
        self._log_messages.clear()

        if job.do_video:
            self.phase_label.setText("Consultando las calidades disponibles")
            self._set_status("comprobando calidad…")
            self._lock()
            t = threading.Thread(target=self._quality_worker, args=(job,), daemon=True)
            t.start()
            return

        self._start_download(job)

    def _start_download(self, job: Job):
        self._set_status("iniciando…")
        self._lock()
        t = threading.Thread(target=self._worker, args=(job,), daemon=True)
        t.start()

    def _quality_worker(self, job: Job):
        try:
            info = self.service.inspect_media(job.url)
            if self.service.is_cancelled():
                raise CancelledError()
            self.signals.quality_ready.emit(job, info)
        except CancelledError:
            self.signals.cancelled.emit("Cancelado por el usuario.")
            self.signals.unlock.emit()
        except Exception as e:
            self.signals.error.emit(f"No se pudo comprobar la calidad.\n\n{e}")
            self.signals.unlock.emit()

    def _on_quality_ready(self, job: Job, info: dict):
        self._unlock()
        dlg = QualityConfirmDialog(self, info)
        if dlg.exec() != QDialog.Accepted:
            self._set_status("listo")
            self._reset_tracking("Descarga cancelada antes de comenzar")
            self._log("Descarga cancelada: no se confirmó la calidad.")
            return

        max_height = dlg.selected_height()
        job = replace(job, max_height=max_height)
        if max_height:
            self._log(f"Calidad elegida: {max_height}p")
        else:
            best = info.get("best_height")
            label = f"{best}p" if best else "máxima disponible"
            self._log(f"Calidad elegida: máxima ({label})")
        self._start_download(job)

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

        # La selección de playlist también se ofrece cuando solo se solicita TXT.
        playlist_url = self._extract_playlist_url(url_raw)
        if playlist_url:
            playlist_only = self.service._is_playlist_url(url)
            question = (
                "¿Quieres procesar TODOS los vídeos de esta playlist con las opciones seleccionadas?"
                if playlist_only else
                "Esta URL incluye una playlist.\n\n"
                "¿Quieres procesar TODA la playlist?\n"
                "Si eliges No, se procesará únicamente el vídeo del enlace."
            )
            if do_transcribe:
                question += "\n\nSe generará un TXT por vídeo y se conservará su MP3."
            reply = QMessageBox.question(
                self, "Procesar playlist", question,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                url = playlist_url
            elif playlist_only:
                return None

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
            self._last_out_dir = job.out_dir if self.service._is_playlist_url(job.url) else (last_dir or job.out_dir)
            self.signals.status.emit("listo")
            preview = outputs[:12]
            message = "Completado:\n\n" + "\n".join(preview)
            if len(outputs) > len(preview):
                message += f"\n\n… y {len(outputs) - len(preview)} archivos más. Consulta la carpeta de salida."
            self.signals.done.emit(message)
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

