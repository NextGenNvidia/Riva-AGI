"""
tests/test_cartesia_tts.py — Live integration test: Cartesia Sonic (latency-critical API path).

Task V2 requirement: test Cartesia Sonic API option and generate sample audio.

What this script does
---------------------
1. Synthesizes the standard sample sentence via Cartesia Sonic (sonic-2).
2. Measures time-to-first-audio (TTFA) and total synthesis time.
3. Saves the raw/WAV audio to output_cartesia.wav.
4. Prints a result summary.

Requirements
------------
- CARTESIA_API_KEY must be set in the environment.
- pip install cartesia sounddevice soundfile

Usage
-----
    export CARTESIA_API_KEY="your_api_key_here"
    python tests/test_cartesia_tts.py

    # Optional: play the audio after generating it
    python tests/test_cartesia_tts.py --play
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running from the project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

try:
    from voice_speech.tts import TTSRouter, RouterContext
    from voice_speech.tts.config import RouterConfig, BackendConfig
    from voice_speech.tts.player import play_audio, save_audio
except ImportError:
    from router import TTSRouter, RouterContext
    from config import RouterConfig, BackendConfig
    from player import play_audio, save_audio

SAMPLE_TEXT = (
    "Hello! This is a test of the text-to-speech system."
)
OUTPUT_DIR = Path(__file__).parent / "output_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "output_cartesia.wav"


def main() -> None:
    parser = argparse.ArgumentParser(description="Cartesia Sonic TTS live test")
    parser.add_argument("--play", action="store_true", help="Play audio after generating")
    parser.add_argument("--model", default="sonic-2", help="Cartesia model ID")
    parser.add_argument("--voice", default="", help="Cartesia voice ID UUID")
    args = parser.parse_args()

    print("\n[Cartesia Sonic TTS Test]")
    print(f"  Text        : {SAMPLE_TEXT!r}")
    print(f"  Backend     : cartesia (model={args.model})")
    print(f"  Output      : {OUTPUT_FILE}")
    print()

    backend_kwargs = {"cartesia_model_id": args.model}
    if args.voice:
        backend_kwargs["cartesia_voice_id"] = args.voice

    config = RouterConfig(backend=BackendConfig(**backend_kwargs))
    router = TTSRouter(config=config)

    status = router.status()
    if not status.get("cartesia"):
        print("ERROR: Cartesia backend is not available.")
        print("  → Set CARTESIA_API_KEY and run: pip install cartesia")
        sys.exit(1)

    t_start = time.monotonic()
    ttfa_ms: float | None = None
    chunks: list[bytes] = []

    print("Synthesizing (streaming)...", end="", flush=True)
    ctx = RouterContext(force_backend="cartesia")

    for chunk in router.stream(SAMPLE_TEXT, ctx):
        if ttfa_ms is None and chunk:
            ttfa_ms = (time.monotonic() - t_start) * 1000
        chunks.append(chunk)

    total_ms = (time.monotonic() - t_start) * 1000
    audio_bytes = b"".join(chunks)

    print(" done.")
    print()
    print(f"  TTFA        : {ttfa_ms:.0f} ms" if ttfa_ms else "  TTFA        : N/A")
    print(f"  Total time  : {total_ms:.0f} ms")
    print(f"  Audio size  : {len(audio_bytes):,} bytes")

    save_audio(audio_bytes, OUTPUT_FILE)
    print(f"  Audio saved : {OUTPUT_FILE}")

    summary = router.logger.get_summary()
    print()
    print("  Session summary:")
    for k, v in summary.items():
        print(f"    {k}: {v}")

    if args.play:
        print()
        print("Playing audio...")
        play_audio(audio_bytes)

    print()
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
