"""
Servicio: yt-dlp + transcripción.
"""
import os
import time
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ..config import TRANSCRIBE_MAX_MINUTES, WhisperModel, find_ffmpeg
from ..signals.signals import Signals
from ..models.models import Job


class CancelledError(Exception):
    """Interrupción solicitada por el usuario."""


class MediaService:
    """Servicio que maneja las operaciones de descarga y transcripción."""

    def __init__(self, signals: Signals):
        self.signals = signals
        self._cancel_event = threading.Event()

    def request_cancel(self) -> None:
        """Solicita la cancelación del trabajo en curso."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        """True si el usuario pidió cancelar."""
        return self._cancel_event.is_set()

    def _is_playlist_url(self, url: str) -> bool:
        """Detecta si la URL parece una playlist de YouTube."""
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query)
            list_id = (qs.get("list") or [None])[0]
            if list_id:
                return True
            # Ej: https://www.youtube.com/playlist?list=...
            return parsed.path.startswith("/playlist")
        except Exception:
            return False

    def fetch_playlist_items(self, url: str, limit: int = 300) -> list[dict]:
        """Devuelve items de una playlist (sin descargar).

        Cada item contiene: idx, title, id, url.
        """
        self._set_download_mode()
        if self.is_cancelled():
            raise CancelledError()

        opts = {
            **self._common_opts(),
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": False,
        }

        self.signals.status.emit("leyendo playlist…")
        self.signals.progress.emit(0)

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            if self.is_cancelled():
                raise CancelledError()
            raise RuntimeError(f"No se pudo leer la playlist. ({e})")

        entries = info.get("entries") or []
        items: list[dict] = []
        for i, e in enumerate(entries, start=1):
            if self.is_cancelled():
                raise CancelledError()
            if limit and i > limit:
                break
            if not isinstance(e, dict):
                continue
            items.append(
                {
                    "idx": i,
                    "title": (e.get("title") or "").strip() or "(sin título)",
                    "id": e.get("id"),
                    "url": e.get("url") or e.get("webpage_url"),
                }
            )

        return items

    def run_job(self, job: Job) -> list[str]:
        """Ejecuta un trabajo completo de descarga/transcripción."""
        outputs: list[str] = []

        # Cada ejecución empieza con cancelación limpia.
        self._cancel_event.clear()

        if self.is_cancelled():
            raise CancelledError()

        if job.do_video:
            self._set_download_mode()
            if self.is_cancelled():
                raise CancelledError()
            self.signals.status.emit("vídeo…")
            self.signals.progress.emit(0)
            video_path = self.download_video(job.url, job.out_dir)
            outputs.append(f"Vídeo: {video_path}")
            self.signals.log.emit(f"OK: Vídeo descargado: {video_path}")

        mp3_path = None
        if job.do_audio or job.do_transcribe:
            self._set_download_mode()
            if self.is_cancelled():
                raise CancelledError()
            self.signals.status.emit("audio…")
            self.signals.progress.emit(0)
            mp3_path = self.download_audio_mp3(job.url, job.out_dir)
            outputs.append(f"Audio: {mp3_path}")
            self.signals.log.emit(f"OK: Audio descargado: {mp3_path}")

        if job.do_transcribe:
            if not mp3_path:
                raise RuntimeError("No hay audio para transcribir.")
            if os.path.isdir(mp3_path):
                raise RuntimeError(
                    "La transcripción para playlists no está soportada todavía. Desactiva "
                    "'Transcribir (TXT)' o usa una URL de vídeo individual."
                )
            if self.is_cancelled():
                raise CancelledError()
            txt_path = self.transcribe_to_txt(mp3_path)
            outputs.append(f"Texto: {txt_path}")
            self.signals.log.emit(f"OK: Transcripción guardada: {txt_path}")

        return outputs

    def download_video(self, url: str, out_dir: str) -> str:
        """Descarga un video en formato MP4 con audio."""
        # Carpeta por vídeo (por título), y dentro el MP4.
        outtmpl = str(Path(out_dir) / "%(title).200s" / "[%(id)s] (VIDEO).%(ext)s")

        opts_best = {
            **self._common_opts(),
            "progress_hooks": [self._download_hook()],
            "outtmpl": outtmpl,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bv*+ba/b/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 8,
        }

        opts_fallback = {
            **self._common_opts(),
            "progress_hooks": [self._download_hook()],
            "outtmpl": outtmpl,
            "format": "best[ext=mp4]/best",
        }

        self.signals.log.emit("Descarga vídeo (MP4 con audio)…")
        if self._is_playlist_url(url):
            # Para playlists, dejamos que yt-dlp descargue todas las entradas.
            opts_best["noplaylist"] = False
            opts_fallback["noplaylist"] = False
            try:
                with YoutubeDL(opts_best) as ydl:
                    ydl.download([url])
                    if self.is_cancelled():
                        raise CancelledError()
                return out_dir
            except Exception as e:
                if self.is_cancelled():
                    raise CancelledError()
                self.signals.log.emit(f"AVISO: fallback en playlist (audio integrado). ({e})")
                with YoutubeDL(opts_fallback) as ydl:
                    ydl.download([url])
                    if self.is_cancelled():
                        raise CancelledError()
                return out_dir

        # Descarga simple (un solo vídeo).
        try:
            with YoutubeDL(opts_best) as ydl:
                info = ydl.extract_info(url, download=True)
                if self.is_cancelled():
                    raise CancelledError()
                return ydl.prepare_filename(info)
        except Exception as e:
            if self.is_cancelled():
                raise CancelledError()
            self.signals.log.emit(f"AVISO: fallback a MP4 progresivo (audio integrado). ({e})")
            with YoutubeDL(opts_fallback) as ydl:
                info = ydl.extract_info(url, download=True)
                if self.is_cancelled():
                    raise CancelledError()
                return ydl.prepare_filename(info)

    def download_audio_mp3(self, url: str, out_dir: str) -> str:
        """Descarga y extrae audio en formato MP3."""
        # Carpeta por vídeo (por título), y dentro el MP3.
        outtmpl = str(Path(out_dir) / "%(title).200s" / "[%(id)s] (AUDIO).%(ext)s")

        opts = {
            **self._common_opts(),
            "progress_hooks": [self._download_hook()],
            "outtmpl": outtmpl,
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "concurrent_fragment_downloads": 8,
        }

        self.signals.log.emit("Descarga audio (MP3)…")
        if self._is_playlist_url(url):
            # Para playlists, dejamos que yt-dlp descargue todas las entradas.
            opts["noplaylist"] = False
            try:
                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
                    if self.is_cancelled():
                        raise CancelledError()
                return out_dir
            except Exception as e:
                if self.is_cancelled():
                    raise CancelledError()
                self.signals.log.emit(f"AVISO: fallo en playlist de audio: ({e}).")
                # Intento con los mismos opts (fallback suave no aplica aquí sin más variantes).
                with YoutubeDL(opts) as ydl:
                    ydl.download([url])
                    if self.is_cancelled():
                        raise CancelledError()
                return out_dir

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base = ydl.prepare_filename(info)
            return os.path.splitext(base)[0] + ".mp3"

    def transcribe_to_txt(self, audio_path: str) -> str:
        """Transcribe un archivo de audio a texto usando Whisper."""
        self._set_transcribe_mode()
        start = time.time()

        limit_seconds = TRANSCRIBE_MAX_MINUTES * 60 if TRANSCRIBE_MAX_MINUTES > 0 else None
        if limit_seconds:
            self.signals.log.emit(f"Transcripción (TXT)… (tope: {TRANSCRIBE_MAX_MINUTES} min)")
        else:
            self.signals.log.emit("Transcripción (TXT)… (sin tope)")
        self.signals.status.emit("transcribiendo…")

        model = self._build_whisper_model()

        segments, _ = model.transcribe(
            audio_path,
            language="es",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
            no_speech_threshold=0.2,
        )

        txt_path = os.path.splitext(audio_path)[0] + ".txt"
        seg_count = 0
        last_ping = start
        cut = False

        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                for s in segments:
                    if self.is_cancelled():
                        raise CancelledError()
                    if self._hit_time_limit(limit_seconds, s):
                        cut = True
                        break

                    seg_count += 1
                    f.write(s.text.strip() + "\n")

                    now = time.time()
                    if now - last_ping >= 3:
                        elapsed = int(now - start)
                        self.signals.log.emit(f"… transcribiendo ({seg_count} segmentos, {elapsed}s)")
                        self.signals.status.emit(f"transcribiendo… ({elapsed}s)")
                        last_ping = now
        except CancelledError:
            # Si cancelas, intentamos no dejar un TXT parcial.
            try:
                if os.path.exists(txt_path):
                    os.remove(txt_path)
            finally:
                self._set_download_mode()
            raise

        elapsed_total = int(time.time() - start)
        if cut:
            self.signals.log.emit(f"AVISO: transcripción recortada al tope ({TRANSCRIBE_MAX_MINUTES} min).")
        self.signals.log.emit(f"OK: Transcripción completada en {elapsed_total}s. Guardado: {txt_path}")
        self.signals.status.emit("transcripción lista")
        self._set_download_mode()
        return txt_path

    # ---------- Helpers ----------
    def _common_opts(self) -> dict:
        """Opciones comunes para yt-dlp."""
        opts = {
            "retries": 20,
            "fragment_retries": 20,
            "extractor_retries": 5,
            "file_access_retries": 10,
            "socket_timeout": 60,
            "continuedl": True,
            "noplaylist": True,
            "quiet": True,
            "skip_unavailable_fragments": False,
            "raise_incomplete_data": True,
        }

        # Agregar ffmpeg_location solo si se encuentra
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            opts["ffmpeg_location"] = ffmpeg_path

        return opts

    def _download_hook(self):
        """Hook para actualizar progreso durante descargas."""

        def hook(d):
            if self.is_cancelled():
                # Provoca que yt-dlp interrumpa la descarga.
                raise DownloadError("Cancelado")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                if total:
                    pct = int(done * 100 / total)
                    self.signals.progress.emit(max(0, min(100, pct)))
                self.signals.status.emit("descargando…")
            elif status == "finished":
                self.signals.status.emit("procesando…")

        return hook

    def _extract_with_fallback(self, url: str, primary_opts: dict, fallback_opts: dict) -> dict:
        """Intenta descargar con opciones primarias, fallback si falla."""
        try:
            with YoutubeDL(primary_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as e:
            self.signals.log.emit(f"AVISO: fallback a MP4 progresivo (audio integrado). ({e})")
            with YoutubeDL(fallback_opts) as ydl:
                return ydl.extract_info(url, download=True)

    def _build_whisper_model(self):
        """Construye el modelo de Whisper para transcripción."""
        if WhisperModel is None:
            raise RuntimeError("faster-whisper no disponible. Instala: python -m pip install -U faster-whisper")
        return WhisperModel("small", device="cpu", compute_type="int8")

    def _hit_time_limit(self, limit_seconds: int | None, segment) -> bool:
        """Verifica si se alcanzó el límite de tiempo en transcripción."""
        if limit_seconds is None:
            return False
        end_t = getattr(segment, "end", None)
        return (end_t is not None) and (end_t >= limit_seconds)

    def _set_transcribe_mode(self):
        """Activa modo de transcripción (barra indeterminada)."""
        self.signals.busy.emit(True)

    def _set_download_mode(self):
        """Activa modo de descarga (barra determinada)."""
        self.signals.busy.emit(False)

