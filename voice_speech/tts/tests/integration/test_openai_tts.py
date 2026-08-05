"""
tests/test_openai_tts.py — Live integration test: OpenAI TTS (API path).

Task V2 requirement: test at least one API option and generate sample audio.

What this script does
---------------------
1. Synthesizes the standard sample sentence via OpenAI TTS (tts-1, voice=alloy).
2. Measures time-to-first-audio (TTFA) and total synthesis time.
3. Saves the audio to output_openai.mp3.
4. Prints a result summary.

Requirements
------------
- OPENAI_API_KEY must be set in the environment.
- pip install openai sounddevice soundfile

Usage
-----
    export OPENAI_API_KEY="sk-..."
    python tests/test_openai_tts.py

    # Optional: play the audio after generating it
    python tests/test_openai_tts.py --play
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

# ---------------------------------------------------------------------------
# Sample sentence used in both API and local tests for direct comparison
# ---------------------------------------------------------------------------
SAMPLE_TEXT = (
    "The quick brown fox jumps over the lazy dog near the riverbank at sunset."
)
OUTPUT_DIR = Path(__file__).parent / "output_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "output_openai.mp3"


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAI TTS live test")
    parser.add_argument("--play", action="store_true", help="Play audio after generating")
    parser.add_argument("--voice", default="alloy", help="OpenAI voice name")
    parser.add_argument("--model", default="tts-1", help="tts-1 or tts-1-hd")
    args = parser.parse_args()

    print("\n[OpenAI TTS Test]")
    print(f"  Text        : {SAMPLE_TEXT!r}")
    print(f"  Backend     : openai ({args.model}, voice={args.voice})")
    print(f"  Output      : {OUTPUT_FILE}")
    print()

    # Build a config that applies the CLI args
    config = RouterConfig(
        backend=BackendConfig(
            openai_model=args.model,
            openai_voice=args.voice,
        )
    )
    router = TTSRouter(config=config)

    # Check availability before attempting synthesis
    status = router.status()
    if not status.get("openai"):
        print("ERROR: OpenAI backend is not available.")
        print("  → Set OPENAI_API_KEY and run: pip install openai")
        sys.exit(1)

    # Streaming synthesis — record TTFA on first chunk
    t_start = time.monotonic()
    ttfa_ms: float | None = None
    chunks: list[bytes] = []

    print("Synthesizing (streaming)...", end="", flush=True)
    ctx = RouterContext(force_backend="openai", voice_id=args.voice)

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

    # Save to file
    save_audio(audio_bytes, OUTPUT_FILE)
    print(f"  Audio saved : {OUTPUT_FILE}")

    # Session log summary
    summary = router.logger.get_summary()
    print()
    print("  Session summary:")
    for k, v in summary.items():
        print(f"    {k}: {v}")

    # Optionally play
    if args.play:
        print()
        print("Playing audio...")
        play_audio(audio_bytes)

    print()
    print("Status: SUCCESS")


if __name__ == "__main__":
    main()
