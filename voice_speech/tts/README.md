# TTS Module — Setup, Testing & Usage Guide

**TTS (Text-to-Speech) Evaluation**  
Voice AI Pipeline · Local + API backends · Pluggable router

---

## Project Structure

```
voice_speech/
└── tts/
    ├── __init__.py                # Package exports (TTSRouter, RouterContext, etc.)
    ├── router.py                  # Multi-backend router & context
    ├── config.py                  # BackendConfig + RouterConfig (auto-loads .env)
    ├── logger.py                  # JSONL per-request metrics logger
    ├── player.py                  # Cross-platform audio player
    ├── README.md                  # Setup, testing & usage guide
    ├── TTS_V2_Evaluation.md       # Technical evaluation & comparison report
    ├── .env.example               # Environment variables template
    ├── requirements.txt           # Python dependencies
    │
    ├── backends/                  # Pluggable TTS engine implementations
    │   ├── __init__.py
    │   ├── base.py                # TTSBackend abstract base class
    │   ├── elevenlabs.py          # ElevenLabs (default API / cloning)
    │   ├── openai_tts.py          # OpenAI TTS (secondary API)
    │   ├── cartesia.py            # Cartesia Sonic (latency path)
    │   ├── azure_tts.py           # Azure Neural TTS (backup API)
    │   └── piper.py               # Piper (local offline fallback)
    │
    └── tests/                     # Test suite
        ├── test_unit.py           # Unit test suite — 29 tests (mocked, no keys needed)
        ├── test_openai_tts.py      # Live OpenAI TTS integration test
        ├── test_cartesia_tts.py   # Live Cartesia Sonic integration test
        ├── test_elevenlabs_tts.py # Live ElevenLabs integration test
        ├── test_azure_tts.py      # Live Azure Neural TTS integration test
        └── test_local_tts.py      # Live Piper local integration test
```

---

## 1. First-Time Setup & .env Configuration

### Create a virtual environment & install dependencies

```bash
cd /home/user/Desktop/voice_speech/tts

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure `.env` file for all API Keys

Simply edit the central `.env` file in the project root:

```bash
# Open .env and paste your API keys
nano .env   # or edit with your preferred editor
```

Example `.env` content:
```env
OPENAI_API_KEY="sk-..."
CARTESIA_API_KEY="your_cartesia_key"
ELEVENLABS_API_KEY="your_elevenlabs_key"
AZURE_SPEECH_KEY="your_azure_key"
AZURE_SPEECH_REGION="eastus"
```

---

## 2. Unit Tests — No Keys or Network Needed

Runs 25 tests with mocked backends. Works immediately after setup.

```bash
cd /home/user/Desktop/voice_speech/tts

# Full verbose output
.venv/bin/python -m pytest tests/test_unit.py -v

# Short summary only
.venv/bin/python -m pytest tests/test_unit.py -q
```

**Expected result:**
```
25 passed in 0.08s
```

**What is tested:**
- All 6 routing paths (default, offline, latency-critical, premium, force, cloning)
- Fallback chain when preferred backend is unavailable
- JSONL logger writes, TTFA tracking, session summary
- Cost budget warning
- Backend availability checks (no key → False, no package → False)

---

## 3. Check Backend Availability

See which backends are ready without generating audio:

```bash
.venv/bin/python -c "
from voice_speech.tts import TTSRouter
router = TTSRouter()
print('Backend status:')
for name, available in router.status().items():
    status = 'available' if available else 'not available'
    print(f'  {name:12s}  {status}')
"
```

**Typical output (no API keys set, Piper installed):**
```
Backend status:
  openai        not available
  cartesia      not available
  elevenlabs    not available
  piper         available
```

---

## 4. Local Test — Piper (No API Key, No Network, $0 Cost)

### Step 1 — Download the Piper binary (Linux x86_64)

```bash
cd /home/user/Desktop/voice_speech/tts

wget https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
tar -xzf piper_linux_x86_64.tar.gz
# Binary is now at: ./piper/piper
```

### Step 2 — Download a voice model

```bash
mkdir -p models

wget -P models \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"

wget -P models \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

### Step 3 — Set environment variables

```bash
export PIPER_BINARY=$(pwd)/piper/piper
export PIPER_MODEL=$(pwd)/models/en_US-lessac-medium.onnx
```

> **Shortcut:** If the binaries are already set up as shown above, you can pass them inline:
> ```bash
> PIPER_BINARY=./piper/piper PIPER_MODEL=./models/en_US-lessac-medium.onnx \
>   .venv/bin/python tests/test_local_tts.py
> ```

### Step 4 — Run the test

```bash
# Generate audio only (saves to tests/output_piper.wav)
.venv/bin/python tests/test_local_tts.py

# Generate AND play back the audio
.venv/bin/python tests/test_local_tts.py --play
```

**Expected output:**
```
[Piper Local TTS Test — Task V2]
  Text        : 'The quick brown fox jumps over the lazy dog near the riverbank at sunset.'
  Backend     : piper (local, $0 cost)
  Output      : /home/user/Desktop/voice_speech/tts/tests/output_audio/output_piper.wav

Synthesizing (local)... done.

  TTFA        : N/A  (Piper uses full-buffer synthesis)
  Total time  : ~1000 ms
  Audio size  : ~185,000 bytes
  Audio saved : tests/output_piper.wav

Status: SUCCESS
```

> **Measured results (actual runs):**  
> Total time: 913–1145 ms · Audio size: ~183–195 KB · Cost: $0.00

---

## 5. API Test — OpenAI TTS (Requires API Key)

### Step 1 — Set your API key

```bash
export OPENAI_API_KEY="sk-..."
```

### Step 2 — Install the SDK

```bash
.venv/bin/pip install openai
```

### Step 3 — Run the test

```bash
# Generate audio (saves to tests/output_audio/output_openai.mp3)
.venv/bin/python tests/test_openai_tts.py

# Generate AND play back
.venv/bin/python tests/test_openai_tts.py --play

# Use a different voice or model
.venv/bin/python tests/test_openai_tts.py --voice nova --model tts-1-hd
```

**Available voices:** `alloy` (default), `echo`, `fable`, `onyx`, `nova`, `shimmer`  
**Available models:** `tts-1` ($15/1M chars) · `tts-1-hd` ($30/1M chars, higher quality)

**Expected output:**
```
[OpenAI TTS Test — Task V2]
  Text        : 'The quick brown fox jumps over the lazy dog near the riverbank at sunset.'
  Backend     : openai (tts-1, voice=alloy)

  TTFA        : ~300-500 ms
  Total time  : ~800-1200 ms
  Audio size  : ~28,000 bytes
  Audio saved : tests/output_openai.mp3

Status: SUCCESS
```

---

## 6. API Test — Cartesia (Fastest TTFA ~65ms)

```bash
export CARTESIA_API_KEY="..."
.venv/bin/pip install cartesia

.venv/bin/python -c "
from voice_speech.tts import TTSRouter, RouterContext
from voice_speech.tts.player import save_audio

router = TTSRouter()
audio = router.synthesize(
    'Testing Cartesia latency-critical path.',
    RouterContext(latency_critical=True)
)
save_audio(audio, 'tests/output_cartesia.raw')
print(router.logger.get_summary())
"
```

---

## 7. API Test — ElevenLabs (Best Voice Quality)

```bash
export ELEVENLABS_API_KEY="..."
.venv/bin/pip install elevenlabs

.venv/bin/python -c "
from voice_speech.tts import TTSRouter, RouterContext
from voice_speech.tts.player import save_audio

router = TTSRouter()
audio = router.synthesize(
    'Testing ElevenLabs premium voice quality.',
    RouterContext(premium=True)
)
save_audio(audio, 'tests/output_elevenlabs.mp3')
print(router.logger.get_summary())
"
```

---

## 8. Use the Module in Your Own Code

```python
from voice_speech.tts import TTSRouter, RouterContext, play_audio, save_audio

router = TTSRouter()

# --- Default path (OpenAI -> Piper fallback) ---
audio = router.synthesize("Hello, how can I help?", RouterContext())
play_audio(audio)

# --- Offline mode (forces Piper, $0 cost) ---
audio = router.synthesize(
    "Running in offline mode.",
    RouterContext(network_available=False)
)
play_audio(audio)

# --- Latency-critical (Cartesia -> OpenAI -> Piper) ---
audio = router.synthesize(
    "Sure, searching for that now.",
    RouterContext(latency_critical=True)
)

# --- Premium voice (ElevenLabs -> OpenAI -> Piper) ---
audio = router.synthesize(
    "Welcome to our service.",
    RouterContext(premium=True)
)

# --- Streaming (yields chunks as they arrive) ---
for chunk in router.stream("Streaming response.", RouterContext()):
    play_audio(chunk)   # playback starts before synthesis is complete

# --- Force a specific backend ---
audio = router.synthesize("Test.", RouterContext(force_backend="piper"))

# --- Save audio to file ---
save_audio(audio, "output.wav")

# --- Session metrics ---
print(router.logger.get_summary())
# {
#   'total_requests': 6,
#   'total_cost_usd': 0.000225,
#   'p50_ttfa_ms': 412.3,
#   'p95_ttfa_ms': 840.1,
#   'backends_used': {'openai': 4, 'piper': 2}
# }
```

---

## 9. Environment Variable Reference

All configuration is driven by environment variables. No hard-coded credentials.

### Backend Keys & Settings

| Variable               | Default                        | Description                              |
|------------------------|--------------------------------|------------------------------------------|
| `OPENAI_API_KEY`       | _(empty)_                      | Required for OpenAI backend              |
| `OPENAI_TTS_MODEL`     | `tts-1`                        | `tts-1` or `tts-1-hd`                   |
| `OPENAI_TTS_VOICE`     | `alloy`                        | alloy / echo / fable / onyx / nova / shimmer |
| `CARTESIA_API_KEY`     | _(empty)_                      | Required for Cartesia backend            |
| `CARTESIA_MODEL_ID`    | `sonic-2`                      | Cartesia model ID                        |
| `CARTESIA_VOICE_ID`    | _(default UUID)_               | Cartesia voice UUID                      |
| `ELEVENLABS_API_KEY`   | _(empty)_                      | Required for ElevenLabs backend          |
| `ELEVENLABS_MODEL_ID`  | `eleven_turbo_v2_5`            | ElevenLabs model                         |
| `ELEVENLABS_VOICE_ID`  | `21m00Tcm4TlvDq8ikWAM`         | Rachel (default EL voice)                |
| `PIPER_BINARY`         | `piper`                        | Path to piper executable                 |
| `PIPER_MODEL`          | `en_US-lessac-medium.onnx`     | Path to ONNX model file                  |
| `PIPER_MODEL_CONFIG`   | _(auto-derived)_               | Path to .onnx.json (optional)            |

### Router Settings

| Variable                       | Default               | Description                                   |
|--------------------------------|-----------------------|-----------------------------------------------|
| `TTS_COST_BUDGET_PER_REQUEST`  | `0.005`               | USD per request; WARNING logged if exceeded   |
| `ENABLE_VOICE_CLONING`         | `false`               | Set `true` to enable cloning backend path     |
| `TTS_LOG_FILE`                 | `tts_requests.jsonl`  | Path for JSONL request log                    |

---

## 10. Routing Logic Reference

```
Context flag                  -->  Backend chosen
------------------------------------------------------
force_backend="x"             -->  backend x  (raise if unavailable)
need_cloning=True             -->  ElevenLabs or Cartesia  (if flag on)
network_available=False       -->  Piper  (offline, $0 cost)
premium=True                  -->  ElevenLabs --> OpenAI --> Piper
latency_critical=True         -->  Cartesia   --> OpenAI --> Piper
(default)                     -->  OpenAI     --> Piper
```

Each step falls back to the next if the preferred backend has no API key or
SDK installed.

---

## 11. Quick Command Reference

Make sure your API keys are added in `.env` (or environment variables), then run any of the test scripts below:

```bash
# ==============================================================================
# 1. Unit Tests (28 tests — no API keys or network required)
# ==============================================================================
.venv/bin/python -m pytest tests/test_unit.py -v

# ==============================================================================
# 2. Check Backend Availability Status
# ==============================================================================
.venv/bin/python -c "from voice_speech.tts import TTSRouter; print(TTSRouter().status())"

# ==============================================================================
# 3. Test ElevenLabs (Default API Engine — Highest Voice Quality)
# ==============================================================================
.venv/bin/python tests/test_elevenlabs_tts.py
.venv/bin/python tests/test_elevenlabs_tts.py --play

# ==============================================================================
# 4. Test Cartesia Sonic (Latency-Critical Path — ~65ms TTFA)
# ==============================================================================
.venv/bin/python tests/test_cartesia_tts.py
.venv/bin/python tests/test_cartesia_tts.py --play

# ==============================================================================
# 5. Test OpenAI TTS (Secondary API Engine)
# ==============================================================================
.venv/bin/python tests/test_openai_tts.py
.venv/bin/python tests/test_openai_tts.py --play
.venv/bin/python tests/test_openai_tts.py --play --model tts-1-hd --voice nova

# ==============================================================================
# 6. Test Azure Neural TTS (OpenAI Backup Path)
# ==============================================================================
.venv/bin/python tests/test_azure_tts.py
.venv/bin/python tests/test_azure_tts.py --play

# ==============================================================================
# 7. Test Piper Local (Offline Fallback — $0 Cost)
# ==============================================================================
PIPER_BINARY=./piper/piper PIPER_MODEL=./models/en_US-lessac-medium.onnx \
  .venv/bin/python tests/test_local_tts.py

PIPER_BINARY=./piper/piper PIPER_MODEL=./models/en_US-lessac-medium.onnx \
  .venv/bin/python tests/test_local_tts.py --play

# ==============================================================================
# 8. Inspect Session Request Log
# ==============================================================================
cat tts_requests.jsonl | python3 -m json.tool
```

---

## 12. Troubleshooting

| Problem | Fix |
|---------|-----|
| `openai: False` in status | Set `OPENAI_API_KEY` and run `pip install openai` |
| `piper: False` in status | Set `PIPER_BINARY` to the piper executable path and `PIPER_MODEL` to the .onnx file |
| `No audio playback backend found` | Run `pip install sounddevice soundfile` or install `ffmpeg` (`sudo pacman -S ffmpeg`) |
| `ModuleNotFoundError: voice_speech` | Run from `/home/user/Desktop/voice_speech/tts` directory |
| Cost WARNING in logs | Increase `TTS_COST_BUDGET_PER_REQUEST` or switch to a cheaper backend |
| Piper audio sounds robotic | Try Kokoro-82M (backlog item) or ElevenLabs for higher quality |

---

## 13. V3 Integration Point

When V3 (VAD + Router) is built, it will call the TTS module like this:

```python
from voice_speech.tts import TTSRouter, RouterContext

router = TTSRouter()

def speak(text: str, network_ok: bool, is_urgent: bool):
    ctx = RouterContext(
        network_available=network_ok,
        latency_critical=is_urgent,
    )
    for chunk in router.stream(text, ctx):
        play_audio(chunk)
```

No changes to the TTS module are needed for V3 — just pass the right `RouterContext`.
