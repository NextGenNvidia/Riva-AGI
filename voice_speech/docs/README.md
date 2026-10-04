# RIVA — Real-Time Voice Communication Engine

**Owner:** Ankit Kumar Singh  
**Date:** 2026-08-23  

An intelligent, real-time bidirectional voice communication engine built for RIVA-AGI, bridging browser Web Audio with Google Gemini Live API for low-latency conversational AI.

---

## Features

- **Bidirectional Live Audio Streaming**: Native 16kHz PCM microphone capture and 24kHz model audio playback over WebSockets.
- **Low-Latency Conversational Turnaround**: Direct audio token streaming designed for sub-second conversational flow.
- **Server-Side Voice Activity Detection (VAD)**: Fine-tunable turn detection with automatic speech onset and completion triggers.
- **Natural Barge-In Interruption**: Instant model speech cancellation when the user begins speaking, synchronized via epoch counters.
- **Dynamic Multi-Voice Selection**: Switch between prebuilt voices (*Aoede, Kore, Puck, Charon, Fenrir*) with automatic session re-handshake.
- **Multilingual Support**: Supports Auto-detect, Hindi, English, and natural conversational Hinglish.
- **Multi-Tier Real-Time Web Grounding Tool**: Automatic live web search supporting **Tavily AI Search**, **NewsAPI**, and zero-key **Google News RSS** across all topics.
- **Cross-Platform Support**: Native 1-click launch scripts for Windows (CMD & PowerShell) and Linux/macOS.
- **Interactive 3D WebGL Interface**: Raymarched gyroid visualizer dynamically reactive to voice RMS amplitude.

---

## Prerequisites

- **Python**: Version `3.10` or higher.
- **Gemini API Key**: Obtainable from [Google AI Studio](https://aistudio.google.com/app/apikey).
- **Modern Web Browser**: Chrome, Edge, Safari, or Firefox with Web Audio API support.
- **Microphone Access**: Web browsers permit microphone access only on `http://localhost`, `http://127.0.0.1`, or secure `https://` domains.

---

## Quick Start

> **Note:** All commands below assume your current working directory is `voice_speech/`. If you are in the project root, navigate to `voice_speech/` first (`cd voice_speech`).

### Step 1 — Configure Environment

Copy the example configuration template to `.env`:

#### On Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

#### On Windows (Command Prompt):
```cmd
copy .env.example .env
```

#### On Linux / macOS:
```bash
cp .env.example .env
```

Add your Gemini API key (and optional Tavily search key) in `.env`:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here

# Optional: Tavily AI Search for rich web grounding
TAVILY_API_KEY=your_tavily_key_here
```

---

### Step 2 — Launch the Application

#### Option A: Automated 1-Click Launchers (Recommended)

- **Windows (PowerShell):**
  ```powershell
  .\run.ps1
  ```
- **Windows (Command Prompt):**
  ```cmd
  run.bat
  ```
- **Linux / macOS:**
  ```bash
  ./run.sh
  ```

*The launcher automatically initializes a `.venv`, synchronizes dependencies from `requirements.txt`, configures `PYTHONPATH`, and starts the server on port 8000.*

---

#### Option B: Manual Setup

##### Windows (PowerShell):
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set project path and run server
$env:PYTHONPATH = ".."
python -m voice_speech.web_server
```

##### Windows (Command Prompt):
```cmd
:: 1. Create and activate virtual environment
python -m venv .venv
call .venv\Scripts\activate.bat

:: 2. Install dependencies
pip install -r requirements.txt

:: 3. Set project path and run server
set PYTHONPATH=..
python -m voice_speech.web_server
```

##### Linux / macOS:
```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the gateway server
python -m web_server
```

---

### Step 3 — Open Voice Interface
Navigate to **[http://localhost:8000](http://localhost:8000)** in your browser and click **Start Riva** to begin speaking.

---

## Configuration Guide

All system parameters are configurable via `.env` or system environment variables.

### A. Gemini API & Model Selection
Configure the Gemini Live model identifier via `GEMINI_MODEL`:
```env
# Ultra-Low-Latency Live Streaming (recommended for fastest speech turnaround, ~300-500ms)
GEMINI_MODEL=gemini-3.1-flash-live-preview

# Higher Token Quota Model (larger context headroom)
# GEMINI_MODEL=gemini-2.5-flash-native-audio-latest
```

| Model Identifier | Latency | Token Quota | Best For |
|---|---|---|---|
| `gemini-3.1-flash-live-preview` | Sub-second (~300–500ms) | 65K tokens | Real-time conversational speed |
| `gemini-2.5-flash-native-audio-latest` | ~2–3 seconds | 1,000,000 tokens | Extended testing & high usage |

*Note: Model availability, context limits, and token quotas depend on Google Gemini API preview releases and your AI Studio tier.*

---

### B. Voice Selection
Set the default system voice in `.env` or switch dynamically via the web interface:
```env
# Options: Aoede, Kore, Puck, Charon, Fenrir
GEMINI_VOICE=Aoede
```
- **Aoede**: Warm, natural, and expressive (Default)
- **Kore**: Smooth, clear, and articulate
- **Puck**: Friendly, energetic, and engaging
- **Charon**: Deep, calm, and authoritative
- **Fenrir**: Crisp, direct, and focused

*Switching Voice in the UI:* When a user selects a different voice in the Settings modal, the client performs a clean re-handshake with `/ws?voice={voice}` to reconfigure the Gemini Live connection with the updated voice configuration.

---

### C. Language & Persona Modes
Set the conversation language mode in the Settings modal:
- **Auto-Detect (Universal)**: Dynamically mirrors whatever language you speak in.
- **Hindi**: Converses fluently in Hindi.
- **English**: Converses in standard international English.
- **Hinglish**: Converses in natural colloquial Indian English + Hindi blend.

---

### D. Real-Time Web Grounding & Tools Architecture

RIVA equips Gemini Live with the `get_latest_news` function tool to retrieve fresh facts, live data, and answers to questions requiring up-to-date knowledge.

```text
User asks: "Who won the match yesterday and what was the score?"
                         ↓
Gemini Live invokes tool: get_latest_news(query="India vs West Indies 3rd ODI score")
                         ↓
              [ Tool Execution Chain ]
                         ↓
  ┌────────────────────────────────────────────────────────┐
  │ 1. Tavily AI Search (if TAVILY_API_KEY is configured) │
  │    → Delivers direct answer + full paragraph snippets  │
  ├────────────────────────────────────────────────────────┤
  │ 2. NewsAPI.org (if NEWS_API_KEY is configured)         │
  │    → Delivers publisher headlines + descriptions       │
  ├────────────────────────────────────────────────────────┤
  │ 3. Universal Google News RSS (Zero-key fallback)       │
  │    → Delivers multi-headline parsed live news feed     │
  └────────────────────────────────────────────────────────┘
                         ↓
FunctionResponse delivered back to Gemini Live session
                         ↓
Gemini synthesizes natural spoken voice response with grounded facts
```

#### Tool Capabilities:
- **Broad, Topic-Agnostic**: Works across world affairs, breaking news, politics, technology, culture, weather, sports statistics, player performances, scientific discoveries, and general knowledge.
- **Follow-up Aware**: When follow-up questions request specific metrics, names, or performance statistics, Gemini invokes the tool to retrieve verified facts rather than guessing.

#### Search Configuration Keys in `.env`:
```env
# Primary: Tavily AI Search (Free tier at https://tavily.com - recommended)
TAVILY_API_KEY=your_tavily_api_key_here

# Alternative: NewsAPI (Optional)
NEWS_API_KEY=your_newsapi_key_here
```
*(If no search keys are configured, RIVA automatically and reliably uses the universal zero-key Google News RSS fallback).*

---

### E. Voice Activity Detection (VAD) Tuning
RIVA uses server-side Voice Activity Detection on Google's infrastructure:

```env
# Look-back buffer in milliseconds (default: 50)
VAD_PREFIX_PADDING_MS=50

# Silence duration required before turn completion (default: 120)
VAD_SILENCE_DURATION_MS=120

# Speech onset sensitivity (START_SENSITIVITY_HIGH / START_SENSITIVITY_LOW)
VAD_START_SENSITIVITY=START_SENSITIVITY_HIGH

# Turn completion sensitivity (END_SENSITIVITY_HIGH / END_SENSITIVITY_LOW)
VAD_END_SENSITIVITY=END_SENSITIVITY_HIGH
```

#### VAD Configuration & Trade-Offs

| Parameter | Function | Trade-Off / Recommendation |
|---|---|---|
| `VAD_PREFIX_PADDING_MS` | Pre-speech audio buffer retained when speech starts | Higher values prevent clipped initial syllables; 50ms provides low latency. |
| `VAD_SILENCE_DURATION_MS` | Silence required before declaring user finished speaking | **Lower (80–120ms):** Faster response, but may interrupt natural mid-sentence pauses.<br>**Higher (250–500ms):** More forgiving for slow speakers, but adds turnaround delay. |
| `VAD_START_SENSITIVITY` | Threshold to detect user speaking | `START_SENSITIVITY_HIGH` catches quiet speech quickly; use `LOW` in noisy environments. |
| `VAD_END_SENSITIVITY` | Threshold to detect speech cessation | `END_SENSITIVITY_HIGH` triggers prompt turnarounds immediately after speaking stops. |

---

### F. Concurrency & Circuit Breaker
```env
# Maximum simultaneous WebSocket voice sessions
MAX_CONCURRENT_SESSIONS=5

# Cooldown duration (seconds) after upstream quota (1011) errors
CIRCUIT_BREAKER_COOLDOWN_SEC=45

# Server Port and Log Level
PORT=8000
LOG_LEVEL=INFO
```

---

## Development & Testing

### Running the Test Suite

#### Windows (PowerShell or CMD):
```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run all test suites
pytest tests/ -v
```

#### Linux / macOS:
```bash
# Activate virtual environment
source .venv/bin/activate

# Run all test suites
pytest tests/ -v
```

### Running in Development Mode (Auto-Reload)

```bash
uvicorn web_server:app --reload --host 127.0.0.1 --port 8000
```

---

## Troubleshooting & FAQ

#### 1. Microphone Permission Denied or Inactive
- **Cause:** Browsers block microphone capture on non-secure HTTP origins.
- **Solution:** Access via `http://localhost:8000` or `http://127.0.0.1:8000`. Use HTTPS for remote hostnames.

#### 2. WebSocket Error 1011 / Quota Exhaustion
- **Cause:** Upstream Gemini API rate limit or concurrency quota reached.
- **Solution:** The gateway trips an automatic 45-second circuit breaker cooldown to prevent connection spam. Wait for the cooldown to reset, or check your API tier in Google AI Studio.

#### 3. `Address already in use` (Port 8000)
- **Cause:** Another process is bound to port 8000.
- **Solution:** Specify a different port:
  - Windows: `$env:PORT="8080"; python -m voice_speech.web_server`
  - Linux: `PORT=8080 ./run.sh`

#### 4. `pip: externally-managed-environment` (PEP 668)
- **Cause:** Modern Linux distributions prevent non-venv global pip installs.
- **Solution:** Use `./run.sh` (or `run.bat` / `run.ps1` on Windows) which manages a virtual environment automatically.

---

## Project Structure

```text
voice_speech/
├── docs/
│   └── README.md              # Documentation & guide
├── engine/                    # Core engine
│   ├── config/
│   │   ├── settings.py        # Settings & VAD config
│   │   └── prompts.py         # System & persona prompts
│   ├── conversation/
│   │   ├── state.py           # Session state
│   │   └── session_manager.py # Concurrency & circuit breaker
│   └── gemini/
│       ├── tools.py           # Multi-tier web tools & dispatch
│       ├── session.py         # Gemini Live config
│       └── streaming.py       # Audio streaming bridge
├── tests/                     # Automated unit tests
├── web/                       # Frontend assets
│   ├── index.html             # 3D UI & settings
│   ├── app.js                 # Audio graph & WS client
│   └── worklet.js             # PCM16 resampler
├── web_server.py              # FastAPI WebSocket gateway
├── run.bat                    # Windows CMD 1-click launcher
├── run.ps1                    # Windows PowerShell 1-click launcher
├── run.sh                     # Linux / macOS runner script
├── requirements.txt           # Python dependencies
└── .env.example               # Environment template
```

---

## License & Contributing

- **License:** Internal / RIVA-AGI Project.
- **Contributing:** Ensure all automated tests pass (`pytest tests/ -v`) before submitting code changes.
