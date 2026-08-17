# TTS (Text-to-Speech) Evaluation — Comparison & Recommendation

**Owner:** Ankit Kumar Singh

**Goal:** Compare TTS options across API and local/open-weight formats for a real-time conversational pipeline (STT → orchestrator → TTS) — covering voice quality, latency, cost, voice cloning, and streaming.

---

## 1. Recommendation Summary

- **Lowest-latency real-time voice agent:** Cartesia (Sonic 4) — the fastest commercial TTS evaluated.
- **Free to start, no card-expiry surprises:** Azure AI Speech (F0 tier) — 500K characters/month free, forever, with streaming.
- **Best quality/cloning if budget allows:** ElevenLabs (Flash v2.5) — best-in-class expressiveness and cloning.
- **Best local/offline, no GPU required:** Piper — the only local option genuinely real-time on CPU alone.
- **Best local quality + cloning (commercial-friendly):** Chatterbox — MIT license, zero-shot cloning, 23 languages.
- **Newly worth evaluating:** Deepgram Aura-2 — bundled STT+TTS, sub-200ms latency, $200 no-expiry credit.

**Working recommendation:** Prototype the router against **Azure (API) + Piper (local)** — both free/cheap, both stream. Swap the API leg to **Cartesia** if latency becomes the bottleneck, or to **Deepgram Aura-2** if a single-vendor STT+TTS bundle is preferred. Swap the local leg to **Chatterbox** or **Kokoro** for better quality or cloning.

---

## 2. API Options

| Model | Voice Quality | Latency | Cost | Cloning | Streaming | Free Tier |
|---|---|---|---|---|---|---|
| **ElevenLabs (Flash v2.5)** | Best-in-class expressiveness, 70+ langs, 5,000+ voices (Eleven v3) | ~75ms TTFB | $50–100/1M chars | Yes — best-in-class instant + professional | Native | ~10K credits/mo, attribution required |
| **OpenAI TTS** | Strong, instructable — tone steerable via prompt | ~150–300ms typical; Realtime API trades this for token throughput | Token-based: $0.60/1M text + $12/1M audio tokens (≈$10–16/1M chars equivalent) | No native cloning | Yes, via Realtime API | One-time (~$5), not guaranteed for new accounts |
| **Azure AI Speech** | Very solid neural voices, 140+ langs; Neural HD near-premium | ~150–300ms; on-prem containers available | $16/1M (Neural), $22/1M (HD) | Yes — custom neural voice (enterprise) | Yes | 500K chars/mo, F0 tier, never expires |
| **Cartesia** | Very good, optimized for speed over max expressiveness | ~40ms TTFA (Sonic 4) — latency leader | ~$37/1M chars (Scale tier) | Limited/emerging | Yes, purpose-built for real-time | Small trial credit |
| **Deepgram Aura-2** (suggested addition) | Solid for short conversational turns; trails specialists on long-form/expressive narration | Sub-200ms baseline, ~90ms optimized per vendor; independent benchmarks report ~313ms P50 TTFA over WebSocket — verify directly before committing | $30/1M PAYG, $27/1M on Growth tier (requires $4K+ prepaid) | No | Yes, WebSocket; 7 languages, 40+ English voices | $200 credit, no expiry, no card required |

> **Deprecation note:** PlayHT (PlayAI) was evaluated but excluded — Meta acquired PlayHT in July 2025 and the standalone API is being wound down. Treat as deprecation-risk.

---

## 3. Local / Self-Hosted Options

| Model | Voice Quality | Speed | Compute | Cloning | Streaming | License |
|---|---|---|---|---|---|---|
| **Piper** | Good, slightly robotic vs. cloud models | ~180x real-time on CPU (10s clip in ~55ms) | CPU-only, runs on RPi 4/5, <1GB RAM | No (pre-trained voices) | Chunked/streamable | MIT |
| **Kokoro-82M** | High-quality 24kHz audio; outperforms larger models in blind tests | Real-time on consumer CPU | ~327MB weights; CPU-only or 2–3GB VRAM | No (54 preset voices) | Chunked output | Apache 2.0 |
| **Orpheus TTS** | Human-like, empathetic; emotion control via `<laugh>`, `<sigh>` tags | ~200ms streaming (~100ms with input streaming) | GPU recommended (3B); smaller variants (150M–400M) CPU-viable | Yes — zero-shot | Yes, real-time | Apache 2.0 |
| **Chatterbox** | Production-grade; open-source ElevenLabs alternative | Turbo variant: sub-200ms | GPU recommended; Turbo (350M) optimized for real-time | Yes — zero-shot, ~5s reference audio, 23 langs | Yes | MIT |
| **Dia** | Ultra-realistic dialogue; multi-speaker via `[S1]`/`[S2]` tags | Real-time on single GPU | ~8GB VRAM recommended | Yes — zero-shot from reference audio | Supported | Apache 2.0 |

**Notable mentions not included above:** Bark (MIT, most expressive/creative but too slow at ~0.8x real-time), XTTS-v2 (best legacy local cloning but non-commercial CPML license, Coqui Inc. defunct), Coqui TTS base toolkit (MPL 2.0, community-maintained, model-dependent quality), Fish Audio (API, not local — reported ~$15/1M chars, positioned as a lower-cost ElevenLabs alternative; worth a look as a sixth API candidate).

---

## 4. Cost at Volume

Assumes ~750 chars/min of spoken audio (1M chars ≈ ~22 hrs); actual ratio varies with speech speed and language (700 chars/min → ~24 hrs, 1000 chars/min → ~16.7 hrs). Local models have $0 per-character cost; GPU-based ones (Orpheus, Chatterbox, Dia) carry separate compute cost not captured here.

| Monthly Volume | ElevenLabs (Flash) | OpenAI TTS | Azure (Neural) | Cartesia | Deepgram Aura-2 | Local (any) |
|---|---|---|---|---|---|---|
| 10 hours (testing) | ~$22.50 | ~$4.50–7.20 | ~$7.20 | ~$16.70 | ~$12.10–13.50 | ~$0 |
| 100 hours (small team) | ~$225 | ~$45–72 | ~$72 | ~$167 | ~$121–135 | ~$0 |
| 1,000 hours (production) | ~$2,250 | ~$450–720 | ~$720 | ~$1,670 | ~$1,210–1,350 | ~$0–50 |

**Break-even:** Piper and Kokoro stay essentially free at any volume (CPU-only, fast) — no volume favors API on cost alone. The reason to pay for an API is quality and cloning, not economics.

---

## 5. Recommendations by Scenario

| If the Pipeline Needs... | Pick | Reasoning |
|---|---|---|
| Fast MVP, free to start | Azure AI Speech (F0) | 500K chars/month free forever, streaming, lowest-risk |
| Lowest-latency real-time agent | Cartesia | ~40ms TTFA, purpose-built for conversation |
| Single-vendor STT + TTS bundle | Deepgram Aura-2 | Sub-200ms, $200 no-expiry credit, unified pipeline |
| Best quality, budget allows | ElevenLabs (Flash v2.5) | ~75ms latency, best cloning + expressiveness |
| High-volume, cost-sensitive | Piper (local) | Effectively free at any scale, CPU-only |
| Lightweight local, better than Piper | Kokoro-82M | 82M params, CPU-viable, Apache 2.0 |
| Voice cloning locally, commercial | Chatterbox | MIT license, 23 langs, sub-200ms Turbo |
| Expressive local with emotion control | Orpheus TTS | Inline emotion tags, zero-shot cloning, Apache 2.0 |
| Multi-speaker dialogue | Dia | Built-in multi-speaker tags, zero-shot cloning |

---

## 6. Notes

- Pricing reflects publicly listed rates as of mid-2026; re-verify before locking in a budget.
- OpenAI TTS, Cartesia, Deepgram, and other externally sourced figures are desk comparisons based on public specs, not hands-on tested. Deepgram Aura-2's time-to-first-audio in particular varies by source (90ms vs. ~313ms P50) — benchmark it directly before relying on either number.
