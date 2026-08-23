"""
Riva: Ultra-Low-Latency Real-Time Voice Assistant.
Powered by Google Gemini Live API with Native Audio Streaming.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import numpy as np
import sounddevice as sd

from .config.settings import Settings
from .conversation.controller import RivaController
from .conversation.state import ConversationState
from .audio.device import list_audio_devices, get_default_devices, print_audio_devices_summary

# Configure clean logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Silence verbose third-party loggers
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)


def print_banner(settings: Settings) -> None:
    defaults = get_default_devices()
    print("=" * 68)
    print("  ⚡ RIVA: Ultra-Low-Latency Voice Assistant (Gemini Live Native Audio)")
    print("=" * 68)
    print(f"  • Model:        {settings.gemini.model}")
    print(f"  • Voice:        {settings.gemini.voice_name}")
    print(f"  • Audio In:     16,000 Hz, 16-bit Mono (20ms frames / 640 bytes)")
    print(f"  • Audio Out:    24,000 Hz, 16-bit Mono (~40ms prebuffer)")
    print(f"  • VAD Silence:  {settings.vad.silence_duration_ms} ms (Prefix: {settings.vad.prefix_padding_ms} ms)")
    mode = settings.audio_in.audio_mode
    detected = "Headset / Earphones 🎧 (Full Duplex — Voice Barge-In Active)" if mode == "headset" else "Built-in Speaker 🔊 (Full Answer Complete — Zero Echo)"
    print(f"  • Audio Mode:   {detected}")
    print(f"  • Default In:   Device index {defaults.get('input')}")
    print(f"  • Default Out:  Device index {defaults.get('output')}")
    print("=" * 68)
    print("  💡 Tip: Press [Enter] anytime while Riva is speaking to interrupt instantly!")
    print("  Press Ctrl+C to exit gracefully.\n")


def on_state_changed(old_state: ConversationState, new_state: ConversationState) -> None:
    icons = {
        ConversationState.DISCONNECTED: "⚪",
        ConversationState.CONNECTING: "🟡",
        ConversationState.CONNECTED: "🟢",
        ConversationState.LISTENING: "👂",
        ConversationState.USER_SPEAKING: "🗣️ ",
        ConversationState.MODEL_RESPONDING: "💭",
        ConversationState.PLAYING_AUDIO: "🔊",
        ConversationState.BARGE_IN: "⚡",
        ConversationState.SESSION_RESUMING: "🔄",
        ConversationState.RECONNECTING: "🟠",
        ConversationState.ERROR: "🔴",
    }
    icon = icons.get(new_state, "•")
    print(f"[{new_state.name.replace('_', ' ')}] {icon}")


def test_microphone(duration_sec: float = 3.0):
    print(f"\n🎤 Testing microphone for {duration_sec} seconds (16kHz mono PCM16)...")
    print(">>> Speak into your microphone now...")
    samples = int(16000 * duration_sec)
    try:
        recording = sd.rec(samples, samplerate=16000, channels=1, dtype="int16", blocking=True)
        raw = recording.flatten()
        rms = np.sqrt(np.mean(raw.astype(np.float32) ** 2))
        max_val = np.max(np.abs(raw))
        print(f"✓ Microphone capture successful! RMS Energy: {rms:.1f} | Peak: {max_val}/32767")
        if rms < 50:
            print("⚠️ Warning: Input signal level is very low. Please check your mic volume.")
    except Exception as e:
        print(f"❌ Microphone test failed: {e}")
        sys.exit(1)


def test_speaker(duration_sec: float = 1.5):
    print(f"\n🔊 Testing speaker playback (24kHz tone)...")
    sample_rate = 24000
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # Generate pleasant 440Hz sine tone (A4)
    tone = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    try:
        sd.play(tone, samplerate=sample_rate, blocking=True)
        print("✓ Speaker test completed successfully!")
    except Exception as e:
        print(f"❌ Speaker test failed: {e}")
        sys.exit(1)


async def async_main(settings: Settings):
    if not settings.gemini.api_key:
        print("\n❌ Error: GEMINI_API_KEY environment variable is not set!")
        print("Please set your API key in .env or export it in your shell:")
        print("  export GEMINI_API_KEY='your_api_key_here'\n")
        sys.exit(1)

    print_banner(settings)

    controller = RivaController(settings)
    controller.state_manager.add_listener(on_state_changed)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        print("\nShutdown signal received. Stopping Riva...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    # Instant [Enter] key interrupter for laptop speaker users
    async def stdin_listener():
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        try:
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            while not stop_event.is_set():
                line = await reader.readline()
                if not line:
                    break
                if controller.audio_playback.is_playing:
                    controller.audio_playback.handle_barge_in()
                    controller.state_manager.transition_to(ConversationState.BARGE_IN)
        except Exception:
            pass

    stdin_task = asyncio.create_task(stdin_listener())

    await controller.start()

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        stdin_task.cancel()
        await controller.stop()
        print("⚡ Riva shut down cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Riva Ultra-Low-Latency Voice Assistant")
    parser.add_argument("--list-devices", action="store_true", help="List all available audio input/output devices")
    parser.add_argument("--test-mic", action="store_true", help="Record and verify microphone input")
    parser.add_argument("--test-speaker", action="store_true", help="Play a test tone on the output device")
    args = parser.parse_args()

    if args.list_devices:
        print_audio_devices_summary()
        return

    if args.test_mic:
        test_microphone()
        return

    if args.test_speaker:
        test_speaker()
        return

    settings = Settings()
    try:
        asyncio.run(async_main(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
