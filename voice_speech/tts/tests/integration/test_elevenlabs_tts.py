"""
tests/integration/test_elevenlabs_tts.py — Live integration test: ElevenLabs (premium quality & cloning path).

Task V2 requirement: test ElevenLabs API option and generate sample audio.

What this script does
---------------------
1. Synthesizes the standard sample sentence via ElevenLabs Turbo v2.5.
2. Measures time-to-first-audio (TTFA) and total synthesis time.
3. Saves the audio to output_elevenlabs.mp3.
4. Prints a result summary.

Requirements
------------
- ELEVENLABS_API_KEY must be set in the environment (or .env).
- pip install elevenlabs sounddevice soundfile

Usage
-----
    export ELEVENLABS_API_KEY="your_api_key_here"
    python tests/integration/test_elevenlabs_tts.py

    # Optional: play the audio after generating it
    python tests/integration/test_elevenlabs_tts.py --play
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow running from project root or voice_speech package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

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
OUTPUT_FILE = OUTPUT_DIR / "output_elevenlabs.mp3"


def main() -> None:
    parser = argparse.ArgumentParser(description="ElevenLabs TTS live test")
    parser.add_argument("--play", action="store_true", help="Play audio after generating")
    parser.add_argument("--model", default="eleven_turbo_v2_5", help="ElevenLabs model ID")
    parser.add_argument("--voice", default="JBFqnCBsd6RMkjVDRZzb", help="ElevenLabs voice ID (George)")
    args = parser.parse_args()

    print("\n[ElevenLabs TTS Test]")
    print(f"  Text        : {SAMPLE_TEXT!r}")
    print(f"  Backend     : elevenlabs (model={args.model}, voice={args.voice})")
    print(f"  Output      : {OUTPUT_FILE}")
    print()

    config = RouterConfig(
        backend=BackendConfig(
            elevenlabs_model_id=args.model,
            elevenlabs_voice_id=args.voice,
        )
    )
    router = TTSRouter(config=config)

    status = router.status()
    if not status.get("elevenlabs"):
        print("ERROR: ElevenLabs backend is not available.")
        print("  → Set ELEVENLABS_API_KEY and run: pip install elevenlabs")
        sys.exit(1)

    t_start = time.monotonic()
    ttfa_ms: float | None = None
    chunks: list[bytes] = []

    print("Synthesizing (streaming)...", end="", flush=True)
    ctx = RouterContext(force_backend="elevenlabs", voice_id=args.voice)

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
