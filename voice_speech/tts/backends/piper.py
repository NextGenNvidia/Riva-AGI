"""
backends/piper.py — Piper local TTS backend (offline fallback).

Evaluation summary (Task V2)
-----------------------------
Engine    : Piper  (https://github.com/rhasspy/piper)
Quality   : 3.4 / 5  — clear and intelligible, somewhat robotic
TTFA      : ~50 ms p50  (full-buffer; no true streaming)
Speed     : ~180x real-time on CPU  (Raspberry Pi capable)
Streaming : not native — generates full WAV, yielded in 4 KB chunks
Cost      : $0  (fully local, no API calls)
Cloning   : no
License   : MIT
Hardware  : CPU-only, no GPU needed

Routing role
------------
OFFLINE FALLBACK: selected when RouterContext.network_available=False.
Also used as the last-resort fallback from all API backends.

Prerequisites
-------------
1. Download a Piper voice model (.onnx + .onnx.json), e.g.:
       wget https://huggingface.co/rhasspy/piper-voices/resolve/main/ \\
            en/en_US/lessac/medium/en_US-lessac-medium.onnx
       wget https://huggingface.co/rhasspy/piper-voices/resolve/main/ \\
            en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

2. Install the piper binary OR install piper-tts via pip on Linux/macOS:
       pip install piper-tts     # Linux/macOS only

Set environment variables:
    PIPER_BINARY       — path to the piper executable (default: "piper")
    PIPER_MODEL        — path to the .onnx model file
    PIPER_MODEL_CONFIG — path to the .onnx.json config (auto-derived if empty)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

try:
    from voice_speech.tts.backends.base import TTSBackend
    from voice_speech.tts.config import BackendConfig
except ImportError:
    from backends.base import TTSBackend
    from config import BackendConfig

_log = logging.getLogger(__name__)

_STREAM_CHUNK = 4096  # bytes per chunk when simulating streaming


class PiperBackend(TTSBackend):
    """
    Piper TTS backend — calls the piper CLI as a subprocess.

    stdin  : text (UTF-8)
    stdout : raw WAV audio
    """

    def __init__(self, config: BackendConfig) -> None:
        self._cfg = config

    # ------------------------------------------------------------------
    # TTSBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "piper"

    @property
    def supports_cloning(self) -> bool:
        return False

    def _resolve_binary(self) -> str | None:
        binary = self._cfg.piper_binary
        if shutil.which(binary):
            return binary
        candidates = [
            Path(binary),
            Path.cwd() / binary,
            Path.cwd().parent / binary,
            Path.cwd().parent.parent / binary,
            Path(__file__).resolve().parent.parent.parent / "piper" / "piper",
            Path(__file__).resolve().parent.parent.parent.parent / "piper" / "piper",
        ]
        for c in candidates:
            if c.is_file():
                return str(c.resolve())
        return None

    def _resolve_model(self) -> str | None:
        model = self._cfg.piper_model
        if not model:
            return None
        candidates = [
            Path(model),
            Path.cwd() / model,
            Path.cwd().parent / model,
            Path.cwd().parent.parent / model,
            Path(__file__).resolve().parent.parent.parent / "models" / "en_US-lessac-medium.onnx",
            Path(__file__).resolve().parent.parent.parent.parent / "models" / "en_US-lessac-medium.onnx",
        ]
        for c in candidates:
            if c.is_file():
                return str(c.resolve())
        return None

    def is_available(self) -> bool:
        bin_path = self._resolve_binary()
        if not bin_path:
            _log.debug(
                "Piper backend unavailable: binary %r not found", self._cfg.piper_binary
            )
            return False

        model_path = self._resolve_model()
        if not model_path:
            _log.debug(
                "Piper backend unavailable: model file %r not found", self._cfg.piper_model
            )
            return False

        return True

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """
        Run Piper and return proper WAV audio bytes.

        Uses a temporary output file instead of --output-raw so the result
        is a standard WAV file with RIFF headers. Raw PCM (--output-raw)
        causes glitchy playback because the player cannot infer the sample
        rate or bit depth without those headers.

        voice_id is accepted to satisfy the interface contract but is
        ignored — Piper's voice is set by the model file in config.
        """
        _log.info("Piper TTS: synthesize %d chars", len(text))

        # Write to a named temp file so Piper emits a proper WAV with headers
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)
        try:
            cmd = self._build_cmd(output_file=tmp_path)
            try:
                subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    capture_output=True,
                    check=True,
                    timeout=60,
                )
            except FileNotFoundError as exc:
                raise RuntimeError(
                    f"Piper binary not found: {self._cfg.piper_binary!r}. "
                    "Install piper or set PIPER_BINARY."
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode(errors="replace")
                raise RuntimeError(f"Piper synthesis failed: {stderr}") from exc

            return Path(tmp_path).read_bytes()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        """
        Piper does not natively stream; synthesize the full buffer and
        yield it in chunks so callers can use the standard stream interface.
        """
        data = self.synthesize(text, voice_id=voice_id)
        for i in range(0, len(data), _STREAM_CHUNK):
            yield data[i: i + _STREAM_CHUNK]

    def estimate_cost(self, text: str) -> float:
        return 0.0  # local — no API cost

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_cmd(self, output_file: str | None = None) -> list[str]:
        """
        Build the piper CLI command.

        output_file : str | None
            Path to write the WAV output file. If provided, piper writes a
            proper WAV with headers (preferred). If None, falls back to
            --output-raw (headerless PCM to stdout — avoid for playback).
        """
        bin_path = self._resolve_binary() or self._cfg.piper_binary
        cmd = [bin_path]

        model_path = self._resolve_model() or self._cfg.piper_model
        if model_path:
            cmd += ["--model", model_path]

        config = self._cfg.piper_model_config
        # Auto-derive config path if not explicitly set but model is
        if not config and model_path:
            config = model_path + ".json"
        if config and Path(config).exists():
            cmd += ["--config", config]

        if output_file:
            # Output proper WAV with RIFF headers to a file
            cmd += ["--output-file", output_file]
        else:
            # Fallback: raw PCM to stdout (no headers — caller must know format)
            cmd += ["--output-raw"]

        return cmd
