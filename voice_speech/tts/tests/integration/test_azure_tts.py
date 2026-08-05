"""
tests/integration/test_azure_tts.py — Live integration test: Azure Neural TTS (OpenAI backup path).

Task V2 requirement: test Azure Neural TTS API option and generate sample audio.

What this script does
---------------------
1. Synthesizes the standard sample sentence via Azure Neural TTS (en-US-AriaNeural).
2. Measures synthesis time and response size.
3. Saves the audio to output_azure.mp3.
4. Prints a result summary.

Requirements
------------
- AZURE_SPEECH_KEY and AZURE_SPEECH_REGION must be set in the environment (or .env).
- pip install azure-cognitiveservices-speech sounddevice soundfile

Usage
-----
    export AZURE_SPEECH_KEY="your_azure_key"
    export AZURE_SPEECH_REGION="eastus"
    python tests/integration/test_azure_tts.py

    # Optional: play the audio after generating it
    python tests/integration/test_azure_tts.py --play
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
OUTPUT_FILE = OUTPUT_DIR / "output_azure.mp3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Azure Neural TTS live test")
    parser.add_argument("--play", action="store_true", help="Play audio after generating")
    parser.add_argument("--voice", default="en-US-AriaNeural", help="Azure Neural voice name")
    parser.add_argument("--region", default="eastus", help="Azure Speech region")
    args = parser.parse_args()

    print("\n[Azure Neural TTS Test]")
    print(f"  Text        : {SAMPLE_TEXT!r}")
    print(f"  Backend     : azure (voice={args.voice}, region={args.region})")
    print(f"  Output      : {OUTPUT_FILE}")
    print()

    config = RouterConfig(
        backend=BackendConfig(
            azure_speech_region=args.region,
            azure_speech_voice=args.voice,
        )
    )
    router = TTSRouter(config=config)

    status = router.status()
    if not status.get("azure"):
        print("ERROR: Azure backend is not available.")
        print("  → Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")
        print("  → Run: pip install azure-cognitiveservices-speech")
        sys.exit(1)

    t_start = time.monotonic()
    ttfa_ms: float | None = None
    chunks: list[bytes] = []

    print("Synthesizing...", end="", flush=True)
    ctx = RouterContext(force_backend="azure", voice_id=args.voice)

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
