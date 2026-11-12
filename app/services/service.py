"""
Servicio: yt-dlp + transcripción.
"""
import os
import time
import threading
from dataclasses import replace
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
        self._whisper_model = None

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

    def fetch_playlist_items(self, url: str, limit: int = 300, *, reset_cancel: bool = True) -> list[dict]:
        """Devuelve items de una playlist (sin descargar).

        Cada item contiene: idx, title, id, url. limit=0 devuelve toda la lista.
        reset_cancel=False conserva la cancelación dentro de un trabajo activo.
        """
        if reset_cancel:
            self._cancel_event.clear()
        self.signals.busy.emit(True)
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

        if not isinstance(info, dict):
            raise RuntimeError("No se pudo obtener la información de la playlist.")
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

    def inspect_media(self, url: str) -> dict:
        """Lee metadatos y calidades de vídeo sin descargar."""
        self._cancel_event.clear()
        if self.is_cancelled():
            raise CancelledError()
        self.signals.status.emit("comprobando calidad…")
        self.signals.log.emit("Comprobando la mejor calidad disponible…")

        if self._is_playlist_url(url):
            return self._inspect_playlist(url)
        return {"is_playlist": False, **self._inspect_single(url)}

    def _inspect_playlist(self, url: str) -> dict:
        opts = {
            **self._common_opts(),
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": False,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if self.is_cancelled():
            raise CancelledError()

        entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
        sample = {}
        if entries:
            first = entries[0]
            vid = first.get("id")
            first_url = first.get("url") or first.get("webpage_url")
            if not first_url and vid:
                first_url = f"https://www.youtube.com/watch?v={vid}"
            if first_url:
                sample = self._inspect_single(first_url)

        return {
            "is_playlist": True,
            "playlist_title": (info.get("title") or "").strip() or "Playlist",
            "count": len(entries),
            **sample,
        }

    def _inspect_single(self, url: str) -> dict:
        opts = {
            **self._common_opts(),
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if self.is_cancelled():
            raise CancelledError()
        if not isinstance(info, dict):
            raise RuntimeError("No se pudo leer la información del vídeo.")

        by_height: dict[int, dict] = {}
        for fmt in info.get("formats") or []:
            if not isinstance(fmt, dict):
                continue
            if (fmt.get("vcodec") or "none") == "none":
                continue
            height = fmt.get("height")
            if not height:
                continue
            fps = fmt.get("fps") or 0
            tbr = fmt.get("tbr") or fmt.get("vbr") or 0
            prev = by_height.get(int(height))
            if not prev or (fps, tbr) > (prev.get("fps") or 0, prev.get("tbr") or 0):
                by_height[int(height)] = {
                    "height": int(height),
                    "fps": fmt.get("fps"),
                    "vcodec": fmt.get("vcodec"),
                    "tbr": tbr,
                }

        heights = sorted(by_height.keys(), reverse=True)
        best_height = heights[0] if heights else info.get("height")
        best_meta = by_height.get(int(best_height)) if best_height else None

        return {
            "title": (info.get("title") or "").strip() or "(sin título)",
            "duration": info.get("duration"),
            "best_height": best_height,
            "best_fps": (best_meta or {}).get("fps") or info.get("fps"),
            "best_vcodec": (best_meta or {}).get("vcodec") or info.get("vcodec"),
            "heights": heights,
            "by_height": by_height,
        }

    def run_job(self, job: Job) -> list[str]:
        """Procesa un vídeo o una playlist, conservando cancelación entre vídeos."""
        self._cancel_event.clear()
        self._whisper_model = None
        if not self._stages_per_video(job):
            raise ValueError("Selecciona al menos una operación.")
        try:
            if self._is_playlist_url(job.url):
                return self._run_playlist(job)
            return self._run_single_job(job)
        finally:
            # Se reutiliza el modelo durante la playlist y se libera al terminar.
            self._whisper_model = None
            self.signals.busy.emit(False)

    @staticmethod
    def _stages_per_video(job: Job) -> int:
        return int(job.do_video) + int(job.do_audio or job.do_transcribe) + int(job.do_transcribe)

    @staticmethod
    def _playlist_video_url(item: dict) -> str:
        """Construye una URL individual sin list= para evitar descargar la lista otra vez."""
        video_id = item.get("id")
        raw = str(item.get("url") or "")
        if not video_id and raw:
            parsed = urlparse(raw)
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
            if not video_id and parsed.hostname in {"youtu.be", "www.youtu.be"}:
                video_id = parsed.path.strip("/").split("/")[0]
            if not video_id and not parsed.scheme and "/" not in raw:
                video_id = raw
        video_id = str(video_id or "")
        if not video_id or not all(c.isascii() and (c.isalnum() or c in "_-") for c in video_id):
            raise RuntimeError("No se pudo identificar el vídeo de esta entrada.")
        return f"https://www.youtube.com/watch?v={video_id}"

    def _run_playlist(self, job: Job) -> list[str]:
        self.signals.stages.emit(0, 1, "Leyendo los vídeos de la playlist")
        # El límite de 300 se mantiene solo para el botón «Ver playlist».
        items = self.fetch_playlist_items(job.url, limit=0, reset_cancel=False)
        if self.is_cancelled():
            raise CancelledError()
        if not items:
            raise RuntimeError("La playlist está vacía o no contiene vídeos accesibles.")

        per_video = self._stages_per_video(job)
        total = len(items) * per_video
        self.signals.log.emit(f"Playlist: {len(items)} vídeos; {total} etapas en total.")
        outputs: list[str] = []
        for index, item in enumerate(items, start=1):
            if self.is_cancelled():
                raise CancelledError()
            title = str(item.get("title") or "(sin título)")
            context = f"Vídeo {index}/{len(items)} · {title[:120]}"
            self.signals.log.emit(f"{context}: iniciando")
            try:
                single = replace(job, url=self._playlist_video_url(item))
                outputs.extend(self._run_single_job(
                    single, completed_before=(index - 1) * per_video,
                    total_stages=total, context=context,
                ))
            except CancelledError:
                raise
            except Exception as exc:
                if self.is_cancelled():
                    raise CancelledError() from exc
                # No anunciar éxito completo si un vídeo no pudo procesarse.
                raise RuntimeError(
                    f"La playlist se ha detenido en {context}.\n"
                    f"Vídeos completados: {index - 1}/{len(items)}.\n"
                    "Los archivos ya guardados se conservan en la carpeta de salida.\n\n"
                    f"Detalle: {exc}"
                ) from exc
        self.signals.log.emit(f"Playlist completada: {len(items)} vídeos.")
        return outputs

    def _run_single_job(
        self, job: Job, *, completed_before: int = 0,
        total_stages: int | None = None, context: str = "",
    ) -> list[str]:
        """Procesa las salidas de un vídeo sin reiniciar la cancelación."""
        outputs: list[str] = []

        if self.is_cancelled():
            raise CancelledError()

        total = total_stages if total_stages is not None else self._stages_per_video(job)
        if not total:
            raise ValueError("Selecciona al menos una operación.")
        completed = completed_before

        def begin(label):
            if self.is_cancelled():
                raise CancelledError()
            self.signals.stages.emit(completed, total, f"{context} — {label}" if context else label)

        def finish():
            nonlocal completed
            if self.is_cancelled():
                raise CancelledError()
            completed += 1
            self.signals.stages.emit(completed, total, "")

        if job.do_video:
            begin("Descargando y procesando vídeo")
            self._set_download_mode()
            if self.is_cancelled():
                raise CancelledError()
            self.signals.status.emit("vídeo…")
            self.signals.progress.emit(0)
            video_path = self.download_video(job.url, job.out_dir, max_height=job.max_height)
            outputs.append(f"Vídeo: {video_path}")
            self.signals.log.emit(f"OK: Vídeo descargado: {video_path}")
            finish()

        mp3_path = None
        if job.do_audio or job.do_transcribe:
            begin("Descargando y convirtiendo audio")
            self._set_download_mode()
            if self.is_cancelled():
                raise CancelledError()
            self.signals.status.emit("audio…")
            self.signals.progress.emit(0)
            mp3_path = self.download_audio_mp3(job.url, job.out_dir)
            outputs.append(f"Audio: {mp3_path}")
            self.signals.log.emit(f"OK: Audio descargado: {mp3_path}")
            finish()

        if job.do_transcribe:
            if not mp3_path:
                raise RuntimeError("No hay audio para transcribir.")
            if os.path.isdir(mp3_path):
                raise RuntimeError(
                    "Se esperaba un archivo de audio individual, pero se recibió una carpeta."
                )
            if self.is_cancelled():
                raise CancelledError()
            begin("Transcribiendo audio a texto")
            txt_path = self.transcribe_to_txt(mp3_path)
            outputs.append(f"Texto: {txt_path}")
            self.signals.log.emit(f"OK: Transcripción guardada: {txt_path}")
            finish()

        return outputs

    def download_video(self, url: str, out_dir: str, max_height: int | None = None) -> str:
        """Descarga un video en formato MP4 con audio."""
        # Título legible e ID para distinguir vídeos con el mismo nombre.
        outtmpl = str(Path(out_dir) / "%(title).80s" / "%(title).100s [%(id)s] (VIDEO).%(ext)s")

        opts_best = self._video_ydl_opts(outtmpl, max_height, with_aac_merge=True)
        opts_fallback = self._video_ydl_opts(outtmpl, max_height, with_aac_merge=False)

        if max_height:
            self.signals.log.emit(f"Descarga vídeo (hasta {max_height}p, contenedor MP4)…")
        else:
            self.signals.log.emit("Descarga vídeo (máxima calidad, contenedor MP4)…")
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
                self.signals.log.emit(f"AVISO: fallback de fusión en playlist. ({e})")
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
                self._log_video_quality(info)
                return ydl.prepare_filename(info)
        except Exception as e:
            if self.is_cancelled():
                raise CancelledError()
            self.signals.log.emit(f"AVISO: fallback de fusión a MP4. ({e})")
            with YoutubeDL(opts_fallback) as ydl:
                info = ydl.extract_info(url, download=True)
                if self.is_cancelled():
                    raise CancelledError()
                self._log_video_quality(info)
                return ydl.prepare_filename(info)

    def download_audio_mp3(self, url: str, out_dir: str) -> str:
        """Descarga y extrae audio en formato MP3."""
        # El TXT heredará este mismo nombre al cambiar la extensión.
        outtmpl = str(Path(out_dir) / "%(title).80s" / "%(title).100s [%(id)s] (AUDIO).%(ext)s")

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
            "windowsfilenames": True,
            "noplaylist": True,
            "quiet": True,
            "skip_unavailable_fragments": False,
            "raise_incomplete_data": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["default", "android"],
                }
            },
        }

        # Agregar ffmpeg_location solo si se encuentra
        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            opts["ffmpeg_location"] = ffmpeg_path

        return opts

    def _video_format(self, max_height: int | None) -> str:
        if max_height:
            return (
                f"bv*[height<={max_height}]+ba/"
                f"b[height<={max_height}]/"
                "bv*+ba/b"
            )
        return "bv*+ba/b"

    def _video_ydl_opts(self, outtmpl: str, max_height: int | None, with_aac_merge: bool) -> dict:
        opts = {
            **self._common_opts(),
            "progress_hooks": [self._download_hook()],
            "outtmpl": outtmpl,
            "format": self._video_format(max_height),
            "format_sort": ["res", "fps", "hdr:12", "vcodec:av01:vp9.2:vp9:h265:h264", "br"],
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 8,
        }
        if with_aac_merge:
            opts["postprocessor_args"] = {
                "merger": ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
            }
        return opts

    def _log_video_quality(self, info: dict | None) -> None:
        """Escribe en el log la resolución realmente descargada."""
        if not isinstance(info, dict):
            return
        if info.get("_type") == "playlist":
            return
        height = info.get("height")
        fps = info.get("fps")
        vcodec = info.get("vcodec") or ""
        bits = f"{height}p" if height else "resolución desconocida"
        extra = []
        if fps:
            extra.append(f"{fps} fps")
        if vcodec and vcodec != "none":
            extra.append(vcodec)
        suffix = f" ({', '.join(extra)})" if extra else ""
        self.signals.log.emit(f"Calidad del vídeo: {bits}{suffix}")

    def _download_hook(self):
        """Hook para actualizar progreso durante descargas."""

        def hook(d):
            if self.is_cancelled():
                # Provoca que yt-dlp interrumpa la descarga.
                raise DownloadError("Cancelado")

            status = d.get("status")
            if status == "downloading":
                self.signals.busy.emit(False)
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                if total:
                    pct = int(done * 100 / total)
                    self.signals.progress.emit(max(0, min(100, pct)))
                self.signals.status.emit("descargando…")
            elif status == "finished":
                self.signals.busy.emit(True)
                self.signals.status.emit("procesando…")

        return hook

    def _extract_with_fallback(self, url: str, primary_opts: dict, fallback_opts: dict) -> dict:
        """Intenta descargar con opciones primarias, fallback si falla."""
        try:
            with YoutubeDL(primary_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as e:
            self.signals.log.emit(f"AVISO: fallback de fusión a MP4. ({e})")
            with YoutubeDL(fallback_opts) as ydl:
                return ydl.extract_info(url, download=True)

    def _build_whisper_model(self):
        """Construye el modelo de Whisper para transcripción."""
        if WhisperModel is None:
            raise RuntimeError("faster-whisper no disponible. Instala: python -m pip install -U faster-whisper")
        if self._whisper_model is None:
            self.signals.status.emit("cargando modelo de transcripción…")
            self._whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        return self._whisper_model

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

