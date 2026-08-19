# STT (Speech-to-Text) Evaluation — Comparison & Recommendation

**Owner:** Kishan Singh
**Goal:** Compare all 9 STT options (5 API + 4 local) across accuracy, latency, language support, streaming, and — most importantly — real cost at different usage volumes — and give one clear recommendation for Riva-AGI's voice pipeline.
**Basis:** Research/desk comparison using publicly published provider pricing and specs (no hands-on API testing performed in this pass).

---

## TL;DR (read this first)

| Use case | Best pick | Why |
|---|---|---|
| Need it working today, low volume, no infra | **OpenAI Whisper API** | Simplest integration, flat $0.006/min, no signup friction beyond one API key |
| Real-time / streaming voice agent | **Deepgram Nova-3** | Purpose-built for streaming, lowest latency, cheapest streaming rate |
| Cheapest API at any volume | **AssemblyAI Universal-2** | Lowest per-hour batch rate of all APIs tested |
| High volume, long-term, own hardware | **faster-whisper (local)** | Zero per-minute cost once running; pays back GPU cost quickly at scale |
| Need 100+ languages, enterprise SLA | **Google Cloud STT / Azure Speech** | Broadest language + compliance coverage, but priciest per minute |

**One-line recommendation:** Start with **OpenAI Whisper API** for quick testing and low volume; move to **faster-whisper (local)** once usage scales past ~150–300 hours/month, since that's roughly where local compute becomes cheaper than any API. If the pipeline needs live/streaming transcription (not just batch), swap the API leg to **Deepgram** instead of Whisper.

---

## 1. Cost Comparison (the part that matters most)

### 1.1 Headline rates

| Option | Type | Rate | Per hour | Notes |
|---|---|---|---|---|
| **OpenAI Whisper API** | API | $0.006/min | **$0.36/hr** | Flat rate, no tiers, batch only |
| **AssemblyAI (Universal-2)** | API | ~$0.0025–0.0035/min | **$0.15/hr** | Cheapest API batch rate; streaming ~$0.0075/min |
| **Deepgram (Nova-3)** | API | $0.0043/min batch | **$0.26/hr** | $0.0077/min streaming ($0.46/hr) |
| **Azure Speech** | API | $0.003/min batch, $0.0167/min real-time | **$0.18/hr batch, $1.00/hr real-time** | Batch is cheap; real-time is 5–6x more expensive |
| **Google Cloud STT** | API | $0.016/min standard | **$1.00/hr** ($2.00/hr streaming) | Most expensive of the 5 APIs |
| **faster-whisper** | Local | $0 per minute | **$0** (compute only) | Needs CPU/GPU you already own or rent |
| **whisper.cpp** | Local | $0 per minute | **$0** (compute only) | Same model family, C++ port, slightly less efficient than faster-whisper |
| **Vosk** | Local | $0 per minute | **$0** (compute only) | Lightweight, lower accuracy, runs on very modest hardware |
| **NVIDIA NeMo** | Local | $0 per minute | **$0** (compute, ideally GPU) | Best local accuracy, but wants a GPU to be practical |

### 1.2 What it actually costs at real volumes

| Monthly volume | Whisper API | AssemblyAI | Deepgram | Azure (batch) | Google | Local (faster-whisper)* |
|---|---|---|---|---|---|---|
| 10 hours (testing) | $3.60 | $1.50 | $2.60 | $1.80 | $10.00 | ~$0 (CPU is fine) |
| 100 hours (small team) | $36 | $15 | $26 | $18 | $100 | ~$0–15 (CPU/light GPU) |
| 1,000 hours (production) | $360 | $150 | $260 | $180 | $1,000 | ~$50–150 (needs a real GPU box) |

*Local cost isn't literally $0 at scale — it's whatever the GPU/server costs you, but that cost doesn't scale per-minute the way API costs do. A single rented GPU instance (~$0.50–1/hr, running continuously ≈ $360–730/month) can typically process far more than 1,000 hours/month of audio, so the more volume you have, the more local wins.

### 1.3 Free tier / testing budget

| Option | Free credit | Roughly how much testing that buys |
|---|---|---|
| OpenAI Whisper API | $5 new-account credit | ~833 minutes (~14 hrs) |
| Deepgram | $200 credit | ~45,000+ minutes (~750 hrs) |
| AssemblyAI | $50 credit | ~330+ hrs (batch) |
| Azure Speech | 5 hrs/month, forever | 5 hrs/month, no card needed |
| Google Cloud STT | Free trial credit ($300 general GCP credit) | Varies, shared with all GCP usage |

### 1.4 Break-even: API vs. Local

- Below ~50–100 hours/month → an API is almost always cheaper and less hassle than standing up local infra.
- Around 150–300 hours/month → local (faster-whisper on a modest GPU) starts costing less than any of the APIs above, since API cost scales linearly with usage but a GPU box has a flat monthly cost.
- Past 1,000+ hours/month → local is clearly cheaper (by 2–7x depending on which API you're comparing against), but you now own the maintenance, uptime, and scaling problem instead of the vendor.

---

## 2. Full Comparison — API Options

| Model | Accuracy | Latency | Cost | Language Support | Streaming |
|---|---|---|---|---|---|
| **OpenAI Whisper API** | High (Whisper large-v2/v3) | Low-moderate; batch only | $0.006/min ($0.36/hr) | 99 languages | No — batch only |
| **Deepgram Nova-3** | High, tuned for real-time | Very low; built for real-time | $0.0043/min batch, $0.0077/min streaming | 50+ languages, real-time code-switching | Yes — native streaming, sub-300ms |
| **AssemblyAI Universal-2/3** | High, strong diarization + summarization add-ons | Moderate (batch), low (streaming) | $0.15–0.21/hr batch, $0.45/hr streaming | Good, English-strong | Yes — streaming supported |
| **Google Cloud STT** | High, mature/enterprise-grade | Low | $1.00/hr standard, $2.00/hr streaming | Very broad (100+ languages) | Yes |
| **Azure Speech** | High, enterprise-grade, MS ecosystem | Low | $0.18/hr batch, $1.00/hr real-time | Very broad, 140+ languages | Yes |

## 3. Full Comparison — Local / Self-Hosted Options

| Model | Accuracy | Compute Requirement | Language Support | Streaming |
|---|---|---|---|---|
| **whisper.cpp** | High (same Whisper models, C++ port) | Lightweight; runs on CPU, GPU optional | Same as Whisper (99 languages) | Limited/experimental |
| **faster-whisper** | High (CTranslate2-optimized Whisper) | More efficient than whisper.cpp; CPU or GPU | Same as Whisper (99 languages) | Limited |
| **Vosk** | Moderate (smaller, lighter models) | Very lightweight; good for edge/low-resource hardware | Decent multi-language, lower accuracy than Whisper-based | Yes — designed for real-time |
| **NVIDIA NeMo** | High, especially with GPU acceleration | Higher compute requirement, benefits from GPU | Good, strongest on English + major languages | Yes — streaming ASR models |

---

## 4. Recommendation by Scenario

| If Riva-AGI needs... | Pick | Reasoning |
|---|---|---|
| Fast MVP / prototype, low volume | OpenAI Whisper API | Cheapest to get running, simplest docs, no infra |
| Real-time voice agent / live captions | Deepgram Nova-3 | Purpose-built for streaming, lowest latency + cheapest streaming rate |
| Lowest possible per-hour API cost | AssemblyAI Universal-2 | Beats every other API on batch $/hr |
| High-volume, cost-sensitive, ongoing | faster-whisper (local) | No per-minute cost; pays back GPU cost quickly at scale |
| Edge device / very limited hardware | Vosk | Lowest compute footprint, trade-off on accuracy |
| Enterprise compliance / broadest language coverage | Google Cloud STT or Azure Speech | 100+ languages, enterprise SLAs, but the priciest options here |

**Overall recommendation for the pipeline:** a hybrid setup — local (faster-whisper) for cost efficiency once volume is meaningful, with an API fallback (Whisper for batch accuracy, Deepgram if streaming is needed) for spikes or when GPU capacity isn't available.

---

## Notes

- Pricing above reflects each provider's publicly listed rates as of the research date; rates change often — spot-check the official pricing page before locking in a decision or a budget.
- No hands-on API testing was performed for this pass, per instruction to prioritize a research-based comparison report over code changes.
- "Local = $0" refers to per-minute API cost only; local options still require compute (a CPU is enough for light use, a GPU is recommended at higher volume/accuracy needs).