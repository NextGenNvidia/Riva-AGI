"""
backends/azure_tts.py — Azure Neural TTS backend (OpenAI API backup path).

Evaluation summary (Task V2)
-----------------------------
Model     : Neural TTS (Azure Cognitive Services Speech)
Quality   : 3.9 / 5
TTFA      : ~200 ms p50
Streaming : Yes (pull-stream via SDK; simulated here as full-buffer)
Cost      : ~$16 / 1M chars (Neural, standard tier)
Cloning   : Custom Neural Voice only (separate product, not used here)
License   : commercial — standard Azure API ToS

Routing role
------------
BACKUP path for OpenAI: added to the default chain as a fallback.
Default chain becomes: OpenAI --> Azure --> Piper

Setup
-----
1. Create an Azure Cognitive Services / Speech resource in the Azure Portal.
2. Copy the key and region from: Resource --> Keys and Endpoint.
3. Install the SDK:
       pip install azure-cognitiveservices-speech

Set environment variables:
    AZURE_SPEECH_KEY     — Azure Speech resource key (required)
    AZURE_SPEECH_REGION  — Azure region, e.g. "eastus" (default: eastus)
    AZURE_SPEECH_VOICE   — Neural voice name (default: en-US-AriaNeural)

Available Neural voices (English examples):
    en-US-AriaNeural      — conversational, friendly  (default)
    en-US-GuyNeural       — professional male
    en-US-JennyNeural     — friendly female
    en-GB-SoniaNeural     — British female
    en-IN-NeerjaNeural    — Indian English female
    Full list: https://aka.ms/speech/voices/neural

References
----------
https://learn.microsoft.com/azure/cognitive-services/speech-service/text-to-speech
https://pypi.org/project/azure-cognitiveservices-speech/
"""

from __future__ import annotations

import io
import logging
from typing import Iterator

try:
    from voice_speech.tts.backends.base import TTSBackend
    from voice_speech.tts.config import BackendConfig
except ImportError:
    from backends.base import TTSBackend
    from config import BackendConfig

_log = logging.getLogger(__name__)

_STREAM_CHUNK = 4096  # bytes per chunk when simulating streaming


class AzureTTSBackend(TTSBackend):
    """
    Azure Neural TTS backend using the azure-cognitiveservices-speech SDK.

    The SDK is imported lazily so the module loads even when the package
    is absent — is_available() returns False in that case.

    Synthesis uses SpeechSynthesizer with audio_config=None to capture
    the output as bytes (MP3 at 16 kHz 128 kbps mono).
    """

    def __init__(self, config: BackendConfig) -> None:
        self._cfg = config

    # ------------------------------------------------------------------
    # TTSBackend interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "azure"

    @property
    def supports_cloning(self) -> bool:
        # Azure Custom Neural Voice is a separate product; not used here.
        return False

    def is_available(self) -> bool:
        if not self._cfg.azure_speech_key:
            _log.debug("Azure backend unavailable: AZURE_SPEECH_KEY not set")
            return False
        if not self._cfg.azure_speech_region:
            _log.debug("Azure backend unavailable: AZURE_SPEECH_REGION not set")
            return False
        try:
            import azure.cognitiveservices.speech  # noqa: F401
            return True
        except ImportError:
            _log.debug(
                "Azure backend unavailable: azure-cognitiveservices-speech not installed"
            )
            return False

    def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        """Return complete MP3 audio bytes from Azure Neural TTS."""
        import azure.cognitiveservices.speech as speechsdk  # type: ignore

        voice = voice_id or self._cfg.azure_speech_voice
        _log.info("Azure TTS: synthesize %d chars, voice=%s", len(text), voice)

        speech_config = self._build_speech_config(voice)
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config,
            audio_config=None,  # capture to memory, not speakers
        )

        result = synthesizer.speak_text_async(text).get()
        self._check_result(result, speechsdk)
        return result.audio_data

    def stream(self, text: str, voice_id: str | None = None) -> Iterator[bytes]:
        """
        Azure SDK does support pull-stream synthesis but the setup is
        complex. Here we synthesize the full buffer and yield it in chunks
        so callers can use the standard stream interface unchanged.
        """
        data = self.synthesize(text, voice_id=voice_id)
        for i in range(0, len(data), _STREAM_CHUNK):
            yield data[i: i + _STREAM_CHUNK]

    def estimate_cost(self, text: str) -> float:
        return len(text) / 1_000_000 * self._cfg.azure_cost_per_1m_chars

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_speech_config(self, voice: str):
        """Create and configure a SpeechConfig instance."""
        import azure.cognitiveservices.speech as speechsdk  # type: ignore

        speech_config = speechsdk.SpeechConfig(
            subscription=self._cfg.azure_speech_key,
            region=self._cfg.azure_speech_region,
        )
        # MP3 output — 16 kHz, 128 kbps, mono
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz128KBitRateMonoMp3
        )
        speech_config.speech_synthesis_voice_name = voice
        return speech_config

    def _check_result(self, result, speechsdk) -> None:
        """Raise a descriptive RuntimeError if synthesis failed."""
        reason = result.reason

        if reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return  # success

        if reason == speechsdk.ResultReason.Canceled:
            details = speechsdk.SpeechSynthesisCancellationDetails.from_result(result)
            if details.reason == speechsdk.CancellationReason.AuthenticationFailure:
                raise RuntimeError(
                    "Azure TTS: authentication failed. "
                    "Check AZURE_SPEECH_KEY and AZURE_SPEECH_REGION."
                )
            raise RuntimeError(
                f"Azure TTS synthesis cancelled: {details.reason} — {details.error_details}"
            )

        raise RuntimeError(f"Azure TTS synthesis failed with reason: {reason}")
