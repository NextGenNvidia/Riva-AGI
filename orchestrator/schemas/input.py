"""
Input Schemas — orchestrator/schemas/input.py
==============================================
Defines the standardized input format for data flowing INTO the Riva-AGI
orchestrator and its child agents.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class InputType(str, Enum):
    """
    Supported input modalities for agent processing.

    Values:
        TEXT        — Plain text input (chat messages, prompts).
        AUDIO       — Audio-only input (voice notes, speech).
        IMAGE       — Image-only input (photos, screenshots).
        MULTIMODAL  — Combination of two or more modalities above.
    """
    TEXT = "text"
    AUDIO = "audio"
    IMAGE = "image"
    MULTIMODAL = "multimodal"


class MediaSourceType(str, Enum):
    """
    Describes HOW a media payload (audio/image) is encoded or referenced.

    Values:
        FILE_PATH — The data field contains a local or cloud file path
                    (e.g., "/data/audio/clip.wav" or "s3://bucket/clip.wav").
        URL       — The data field contains an HTTP/HTTPS URL pointing to the
                    media resource (e.g., "https://cdn.example.com/img.png").
        BASE64    — The data field contains base64-encoded binary content,
                    ready to be decoded in-memory without any network calls.
    """
    FILE_PATH = "file_path"
    URL = "url"
    BASE64 = "base64"


# ============================================================================
# MODELS
# ============================================================================

class MediaPayload(BaseModel):
    """
    Structured wrapper around a single media attachment (audio OR image).

    Instead of a bare string, every media field now carries:
      • source_type  — Tells the receiver how to interpret `data`.
      • data         — The actual content (path string, URL, or base64 blob).
      • mime_type    — Optional MIME type hint (e.g., "audio/wav", "image/png").

    Example usage:
        MediaPayload(
            source_type=MediaSourceType.URL,
            data="https://cdn.example.com/voice_note.wav",
            mime_type="audio/wav"
        )
    """
    source_type: MediaSourceType = Field(
        ...,
        description="How to interpret the `data` field: file path, URL, or base64."
    )
    data: str = Field(
        ...,
        description="The media content — a file path, URL, or base64 string."
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="Optional MIME type hint (e.g., 'audio/wav', 'image/png')."
    )


class InputData(BaseModel):
    """
    Standardized schema for inputs sent to agents or orchestrator.

    Supports:
        • Multi-modal inputs: Text, Audio, and/or Image data.
        • Typed media payloads via MediaPayload (no more ambiguous strings).
        • Contextual metadata: Mood signals, user ID, session state, etc.

    Data flow:
        User / Frontend  --->  InputData  --->  Root Orchestrator  --->  Agent
    """
    input_type: InputType = Field(
        ...,
        description="Primary modality of the input payload (text, audio, image, multimodal)."
    )
    text_content: Optional[str] = Field(
        default=None,
        description="Text message, system prompt, or transcribed audio query."
    )
    audio_data: Optional[MediaPayload] = Field(
        default=None,
        description="Structured audio payload with explicit source type."
    )
    image_data: Optional[MediaPayload] = Field(
        default=None,
        description="Structured image payload with explicit source type."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Flexible key-value map for contextual metadata.  "
            "Common keys: user_id, session_id, mood_signals (sentiment, urgency, tone)."
        )
    )
