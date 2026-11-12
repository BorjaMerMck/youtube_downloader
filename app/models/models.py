"""
Modelos de datos / DTOs.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    """Representa un trabajo de descarga/transcripción."""

    url: str
    out_dir: str
    do_video: bool
    do_audio: bool
    do_transcribe: bool
    max_height: int | None = None

