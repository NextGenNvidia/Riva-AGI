"""
tests/integration/test_local_tts.py — Live integration test: Piper (local path).

Task V2 requirement: test at least one local option and generate sample audio.

What this script does
---------------------
1. Synthesizes the standard sample sentence via Piper (fully local, $0 cost).
2. Measures total synthesis time (Piper has no true TTFA — full-buffer only).
3. Saves the audio to output_piper.wav.
4. Prints a result summary.

Requirements
------------
- Piper binary installed (automatically detected, or set via PIPER_BINARY).
- Piper voice model downloaded (automatically detected, or set via PIPER_MODEL).
- No API key or network access needed.

Usage
-----
    python tests/integration/test_local_tts.py

    # Optional: play the audio after generating it
    python tests/integration/test_local_tts.py --play
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
    from voice_speech.tts.player import play_audio, save_audio
except ImportError:
    from router import TTSRouter, RouterContext
    from player import play_audio, save_audio

# ---------------------------------------------------------------------------
# Same sample sentence used across all tests for direct comparison
# ---------------------------------------------------------------------------
SAMPLE_TEXT = (
    "Hello! This is a test of the text-to-speech system."
)
OUTPUT_DIR = Path(__file__).parent / "output_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "output_piper.wav"


def main() -> None:
    parser = argparse.ArgumentParser(description="Piper local TTS test")
    parser.add_argument("--play", action="store_true", help="Play audio after generating")
    args = parser.parse_args()

    print("\n[Piper Local TTS Test]")
    print(f"  Text        : {SAMPLE_TEXT!r}")
    print(f"  Backend     : piper (local, $0 cost)")
    print(f"  Output      : {OUTPUT_FILE}")
    print()

    router = TTSRouter()

    # Check availability before attempting synthesis
    status = router.status()
    if not status.get("piper"):
        print("ERROR: Piper backend is not available.")
        print("  → Install the piper binary and set PIPER_BINARY + PIPER_MODEL.")
        print("  → See Quick Setup in this file's docstring.")
        sys.exit(1)

    # Full-buffer synthesis (Piper generates WAV in one shot)
    t_start = time.monotonic()
    print("Synthesizing (local)...", end="", flush=True)

    ctx = RouterContext(network_available=False)  # force local path
    audio_bytes = router.synthesize(SAMPLE_TEXT, ctx)

    total_ms = (time.monotonic() - t_start) * 1000
    print(" done.")
    print()
    print("  TTFA        : N/A  (Piper uses full-buffer synthesis)")
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
