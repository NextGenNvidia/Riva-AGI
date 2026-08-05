"""
player.py — Cross-platform audio playback helper.

Supports two modes:

1. Full-buffer playback — pass raw bytes (WAV or MP3)
2. Streaming playback   — pass an Iterator[bytes]; chunks are collected and then played
   (for low-latency streaming playback, replace _play_stream with a ring-buffer implementation).

Playback strategy (tried in order):
    a. sounddevice + soundfile  (best cross-platform, WAV/MP3/OGG)
    b. sounddevice + numpy      (WAV only, no soundfile dependency)
    c. subprocess: aplay        (Linux ALSA, WAV)
    d. subprocess: afplay       (macOS, any format)
    e. subprocess: ffplay       (cross-platform if ffmpeg is installed)

If none are available, the function raises RuntimeError with a helpful
message listing what to install.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def play_audio(audio: bytes | Iterator[bytes]) -> None:
    """
    Play audio from bytes or a streaming iterator.

    Parameters
    ----------
    audio : bytes | Iterator[bytes]
        Either the complete audio as bytes, or an iterator that yields
        audio chunks. In streaming mode playback starts after all chunks
        are collected (for a ring-buffer approach, replace _play_stream).
    """
    if isinstance(audio, (bytes, bytearray)):
        _play_bytes(audio)
    else:
        _play_stream(audio)


def save_audio(data: bytes, path: str | Path) -> None:
    """Save raw audio bytes to *path*."""
    Path(path).write_bytes(data)
    _log.info("Audio saved to %s (%d bytes)", path, len(data))


# ---------------------------------------------------------------------------
# Internal — full-buffer path
# ---------------------------------------------------------------------------

def _play_bytes(data: bytes) -> None:
    if not data:
        _log.warning("play_audio: received empty audio bytes, nothing to play")
        return
    if _try_sounddevice(data):
        return
    if _try_subprocess(data):
        return
    raise RuntimeError(
        "No audio playback backend found. "
        "Install sounddevice+soundfile ('pip install sounddevice soundfile'), "
        "or ensure aplay / afplay / ffplay is in PATH."
    )


def _try_sounddevice(data: bytes) -> bool:
    """Attempt playback via sounddevice + soundfile (best cross-platform)."""
    try:
        import sounddevice as sd  # type: ignore
        import soundfile as sf    # type: ignore

        buf = io.BytesIO(data)
        audio_array, samplerate = sf.read(buf, dtype="float32")
        sd.play(audio_array, samplerate=samplerate)
        sd.wait()
        return True
    except Exception as exc:
        _log.debug("sounddevice/soundfile playback failed: %s", exc)
        return False


def _try_subprocess(data: bytes) -> bool:
    """Try system CLI players in order of preference."""
    for cmd in _subprocess_commands():
        try:
            subprocess.run(
                cmd,
                input=data,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            _log.debug("subprocess player %s failed: %s", cmd[0], exc)
    return False


def _subprocess_commands() -> list[list[str]]:
    cmds: list[list[str]] = []
    if shutil.which("aplay"):    # Linux ALSA (WAV)
        cmds.append(["aplay", "-q", "-"])
    if shutil.which("afplay"):   # macOS (any format)
        cmds.append(["afplay", "-"])
    if shutil.which("ffplay"):   # cross-platform (ffmpeg)
        cmds.append([
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-i", "pipe:0"
        ])
    return cmds


# ---------------------------------------------------------------------------
# Internal — streaming path
# ---------------------------------------------------------------------------

def _play_stream(chunks: Iterator[bytes]) -> None:
    """
    Collect all chunks, then play the assembled buffer.

    For very-low-latency use cases, a ring-buffer approach can replace
    this simple collect-then-play implementation. See backlog in PRD §12.
    """
    buf = io.BytesIO()
    for chunk in chunks:
        if chunk:
            buf.write(chunk)

    data = buf.getvalue()
    if not data:
        _log.warning("play_audio: stream yielded no audio data")
        return
    _play_bytes(data)
