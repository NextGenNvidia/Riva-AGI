# RIVA — Real-Time Voice Communication Engine

Owner: Ankit Kumar Singh

Date: 23/08/2026

An intelligent, real-time voice communication module built for the RIVA-AGI.

---

## Features

- **Bidirectional Live Audio Streaming**: Native 16kHz PCM capture and 24kHz audio playback via WebSockets.
- **Server-Side Voice Activity Detection (VAD)**: Immediate turn turnaround with automatic speech onset and completion detection.
- **Zero-Latency Turnaround**: Streamlined Gemini Live pipeline with direct audio token generation.
- **Dynamic Multi-Voice Selection**: Real-time switching between prebuilt voices (Aoede, Kore, Puck, Charon, Fenrir).
- **Multilingual Support**: Real-time support for Auto-detect, Hindi, English, and natural conversational Hinglish.
- **Interactive 3D WebGL Interface**: Raymarched gyroid visualizer with dynamic RMS time-domain voice reactivity.

---

## Directory Structure

```text
voice_speech/
├── docs/
│   └── README.md              # Voice engine documentation & config guide
├── engine/                    # Core configuration & settings
│   └── config/
│       ├── settings.py        # System environment & VAD dataclasses
│       └── prompts.py         # System instructions & multilingual persona prompts
├── web/
│   ├── index.html             # WebGL 3D interface & settings modal
│   ├── app.js                 # Web Audio graph & WebSocket client
│   └── worklet.js             # High-performance PCM16 resampler worklet
├── web_server.py              # FastAPI WebRTC Gateway & Live Bridge
├── run.sh                     # Voice gateway runner script
├── requirements.txt           # Voice module dependencies
└── .env.example               # Environment configuration template
```

---

## Quick Start

### 1. Configure Environment
Copy the example environment template into your project root:
```bash
cp voice_speech/.env.example .env
```

### 2. Install Dependencies
```bash
pip install -r voice_speech/requirements.txt
```

### 3. Launch Voice Interface
```bash
./voice_speech/run.sh
```
Open **`http://localhost:8000`** in your browser and click **Start Riva**.

---

## Configuration Guide (Model, API & Settings)

All configuration is managed via environment variables in the `.env` file or exported in your shell.

### 1. API Key Setup
Obtain your Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
```env
# Required for real-time speech streaming
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

---

### 2. Model Selection
RIVA supports Google's bidirectional Live API models:

```env
# Ultra-Low-Latency Live Streaming (Recommended for fastest speech turnaround ~300-500ms)
GEMINI_MODEL=gemini-3.1-flash-live-preview

# Higher Token Quota Model (1 Million token headroom)
# GEMINI_MODEL=gemini-2.5-flash-native-audio-latest
```

| Model Identifier | Latency | Token Quota | Best For |
|---|---|---|---|
| `gemini-3.1-flash-live-preview` | **Sub-second (~300-500ms)** | 65K tokens | Real-time conversational speed |
| `gemini-2.5-flash-native-audio-latest` | ~2-3 seconds | 1,000,000 tokens | Extended testing & high usage |

---

### 3. Voice Selection
You can set the default system voice in `.env`, or switch dynamically at any time using the Settings modal in the web interface:

```env
# Available Voices: Aoede, Kore, Puck, Charon, Fenrir
GEMINI_VOICE=Aoede
```

- **Aoede**: Warm, natural, and expressive (Recommended)
- **Kore**: Smooth, clear, and articulate
- **Puck**: Friendly, energetic, and engaging
- **Charon**: Deep, calm, and authoritative
- **Fenrir**: Strong, direct, and crisp

---

### 4. Language & Accent Modes
RIVA automatically adapts to the user's spoken language or can be locked to a specific mode via the Web UI Settings:

- **Auto-Detect (Universal)**: Dynamically mirrors whatever language you speak in (Hindi, English, Spanish, Japanese, etc.).
- **Hindi**: Speaks fluently in natural, everyday Hindi.
- **English**: Speaks in fluent, standard international English.
- **Hinglish**: Uses a natural blend of Hindi and English as commonly spoken in India.

---

### 5. Server-Side VAD (Voice Activity Detection) Tuning
Fine-tune speech turn completion and interruption sensitivity:

```env
# Fast 50ms look-back buffer
VAD_PREFIX_PADDING_MS=50

# Fast 120ms turn turnaround upon question completion
VAD_SILENCE_DURATION_MS=120

# Speech onset sensitivity (START_SENSITIVITY_HIGH / START_SENSITIVITY_LOW)
VAD_START_SENSITIVITY=START_SENSITIVITY_HIGH

# Turn completion sensitivity (END_SENSITIVITY_HIGH / END_SENSITIVITY_LOW)
VAD_END_SENSITIVITY=END_SENSITIVITY_HIGH
```

---

### 6. Server, Concurrency & Circuit Breaker
```env
# Maximum concurrent WebSocket sessions (default: 5)
MAX_CONCURRENT_SESSIONS=5

# Rate limit cooldown duration in seconds after 1011 quota exhaustion (default: 45)
CIRCUIT_BREAKER_COOLDOWN_SEC=45

# Server Port and Log Level
PORT=8000
LOG_LEVEL=INFO
```

---

### 7. Optional Real-Time News Grounding
RIVA includes built-in live news lookups using Google News RSS (zero key required). If you have a NewsAPI account, you can optionally provide your API key:

```env
# Optional NewsAPI.org key (falls back to Google News RSS automatically if empty)
NEWS_API_KEY=your_news_api_key_here
```
