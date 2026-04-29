"""
Configuración y utilidades del proyecto.
"""
import os
import shutil

# =========================
# Configuración (ajusta esto)
# =========================
FFMPEG_DIR = r"C:\ffmpeg\bin"  # Si FFmpeg está en PATH, déjalo como None
TRANSCRIBE_MAX_MINUTES = 0  # 0 = sin tope

# Importación condicional de faster-whisper
try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None


def find_ffmpeg() -> str | None:
    """Intenta encontrar FFmpeg en el sistema."""
    # Si FFMPEG_DIR está configurado y existe, úsalo
    if FFMPEG_DIR and os.path.exists(FFMPEG_DIR):
        ffmpeg_exe = os.path.join(FFMPEG_DIR, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if os.path.exists(ffmpeg_exe):
            return FFMPEG_DIR

    # Buscar en PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return os.path.dirname(ffmpeg_path)

    return None

