"""
Riva WebRTC Gateway Server (FastAPI + WebSocket).
Persistent, non-disconnecting bridge between browser WebRTC and Gemini Live API.
"""

import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from google import genai
from google.genai import types, errors
import numpy as np

try:
    from voice_speech.engine.config.settings import Settings
except ImportError:
    try:
        from .engine.config.settings import Settings
    except ImportError:
        from engine.config.settings import Settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("riva.web_server")

settings = Settings()

# Validate API key at startup (fail fast with a helpful message)
if not settings.gemini.api_key:
    logger.error(
        "GEMINI_API_KEY is not set! "
        "Copy voice_speech/.env.example to .env and add your key from https://aistudio.google.com/app/apikey"
    )
    sys.exit(1)

# Pre-warmed Gemini client singleton
genai_client = genai.Client(api_key=settings.gemini.api_key)


async def fetch_news_summary(query: str) -> str:
    """Fetches real-time news headlines via NewsAPI or live Google News RSS with strict ~300-char token capping."""
    clean_query = query.strip()
    news_api_key = os.getenv("NEWS_API_KEY", "").strip()
    loop = asyncio.get_event_loop()

    # 1. Option A: NewsAPI.org (if NEWS_API_KEY is configured in .env)
    if news_api_key:
        try:
            encoded = urllib.parse.quote(clean_query)
            url = f"https://newsapi.org/v2/everything?q={encoded}&pageSize=3&sortBy=publishedAt&apiKey={news_api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "RivaVoice/1.0"})

            def _fetch_newsapi():
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            data = await loop.run_in_executor(None, _fetch_newsapi)
            articles = data.get("articles", [])
            headlines = [a["title"] for a in articles[:3] if a.get("title")]
            if headlines:
                summary = " | ".join(headlines)[:320]
                logger.info(f"NewsAPI raw response for '{clean_query}': {summary!r}")
                return summary
        except Exception as e:
            logger.warning(f"NewsAPI fetch failed ({e}), falling back to live News RSS...")

    # 2. Option B: Live News RSS Feed (100% Free, Zero-Key, Real-Time Breaking News)
    try:
        encoded = urllib.parse.quote(clean_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

        def _fetch_rss():
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                return resp.read()

        xml_data = await loop.run_in_executor(None, _fetch_rss)
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")

        headlines = []
        for item in items[:3]:
            title = item.find("title")
            if title is not None and title.text:
                clean_title = title.text.split(" - ")[0] if " - " in title.text else title.text
                headlines.append(clean_title)

        if headlines:
            summary = " | ".join(headlines)[:320]
            logger.info(f"Live News RSS response for '{clean_query}': {summary!r}")
            return summary

        return f"No recent breaking news found for '{clean_query}'."
    except Exception as e:
        logger.warning(f"News RSS fetch error for '{clean_query}': {e}")
        return f"Could not retrieve recent news for '{clean_query}'."

app = FastAPI(title="Riva WebRTC Gateway")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

# Concurrent session limiter — prevents unbounded quota burn
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "5"))
_active_sessions = 0
_session_lock = asyncio.Lock()


@app.get("/")
async def get_index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


@app.get("/app.js")
async def get_app_js():
    return FileResponse(os.path.join(WEB_DIR, "app.js"))


@app.get("/worklet.js")
async def get_worklet_js():
    return FileResponse(os.path.join(WEB_DIR, "worklet.js"))


@app.get("/favicon.ico")
async def get_favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="#4dbc1b"/></svg>'
    return Response(content=svg, media_type="image/svg+xml")


@app.websocket("/ws")
async def audio_websocket_endpoint(websocket: WebSocket):
    global _active_sessions

    # Origin validation — only allow localhost and same-origin connections
    origin = websocket.headers.get("origin", "")
    allowed_origins = {"http://localhost:8000", "http://localhost", "http://127.0.0.1:8000", "https://localhost:8000"}
    if origin and origin not in allowed_origins:
        logger.warning(f"Rejected WebSocket from unauthorized origin: {origin}")
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # Enforce concurrent session cap
    async with _session_lock:
        if _active_sessions >= MAX_CONCURRENT_SESSIONS:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": f"Server at capacity ({MAX_CONCURRENT_SESSIONS} sessions). Try again later."})
            await websocket.close(code=4029)
            return
        _active_sessions += 1

    try:
        await websocket.accept()
    except Exception:
        async with _session_lock:
            _active_sessions -= 1
        return

    # Read voice and language directly from query parameters
    voice = websocket.query_params.get("voice") or "Aoede"
    language = websocket.query_params.get("language") or "auto"
    logger.info(f"Browser WebRTC client connected to /ws (voice={voice}, language={language}) [{_active_sessions}/{MAX_CONCURRENT_SESSIONS} sessions]")

    client = genai_client
    mic_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=30)
    current_epoch = 0
    ws_lock = asyncio.Lock()
    session_active = True

    # Dynamic Voice Selection
    valid_voices = {"Aoede", "Kore", "Puck", "Charon", "Fenrir"}
    selected_voice = voice if voice in valid_voices else settings.gemini.voice_name

    # Dynamic System Instruction with Unified Voice Architecture
    base_instruction = (
        "You are Riva, an intelligent real-time conversational voice assistant "
        "built by NextGen SuperComputing Club at KIET.\n\n"
        "CORE RULES:\n"
        "1. Understand the user's speech accurately and answer their actual question directly.\n"
        "2. Keep responses concise, clear, natural, and conversational unless the user asks for detail.\n"
        "3. Speak naturally as a voice assistant. Do not sound robotic or overly formal.\n"
        "4. Never narrate internal actions or processes such as 'Thinking', 'Processing', or 'Searching'.\n"
        "5. Do not describe actions you are performing. Give the answer directly.\n"
        "6. Maintain natural conversational context across turns.\n"
        "7. If the user asks a follow-up question, use relevant context from the conversation.\n"
    )

    if language == "hindi":
        instruction = base_instruction + (
            "\nLANGUAGE:\n"
            "Respond primarily in fluent, natural Hindi.\n"
            "Use English technical terms only when they are commonly used or make the explanation clearer.\n"
        )
    elif language == "english":
        instruction = base_instruction + (
            "\nLANGUAGE:\n"
            "Respond in fluent, natural English.\n"
        )
    elif language == "hinglish":
        instruction = base_instruction + (
            "\nLANGUAGE:\n"
            "Respond in natural conversational Hinglish, using a comfortable mix of Hindi and English "
            "as commonly spoken in everyday conversations in India.\n"
            "Do not force unnecessary translations of common English technical terms.\n"
        )
    else:  # auto / universal multilingual
        instruction = base_instruction + (
            "\nLANGUAGE & ACCENT DIRECTIVE:\n"
            "- You are fully multilingual. Listen carefully to the language the user speaks in.\n"
            "- Reply in the exact same language or language mix the user is speaking in.\n"
            "- If the user speaks in Hindi, reply directly in natural Hindi.\n"
            "- If the user speaks in English, reply directly in natural English.\n"
            "- If the user speaks in Hinglish (mix of Hindi & English), reply directly in natural, everyday conversational Hinglish.\n"
            "- If the user speaks in any other language (Spanish, French, German, Japanese, etc.), reply directly in that language.\n"
            "- Keep your spoken pronunciation and tone completely natural for that language."
        )

    # Configure Gemini Live Session
    vad_config = types.AutomaticActivityDetection(
        disabled=settings.vad.disabled,
        start_of_speech_sensitivity=getattr(
            types.StartSensitivity,
            settings.vad.start_sensitivity,
            types.StartSensitivity.START_SENSITIVITY_LOW,
        ),
        end_of_speech_sensitivity=getattr(
            types.EndSensitivity,
            settings.vad.end_sensitivity,
            types.EndSensitivity.END_SENSITIVITY_HIGH,
        ),
        prefix_padding_ms=settings.vad.prefix_padding_ms,
        silence_duration_ms=settings.vad.silence_duration_ms,
    )

    speech_config = types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name=selected_voice
            )
        )
    )

    # Thinking config: None for instantaneous zero-latency voice generation
    thinking_config = None
    if settings.gemini.thinking_level.upper() in ("HIGH", "MEDIUM"):
        thinking_level = getattr(types.ThinkingLevel, settings.gemini.thinking_level, types.ThinkingLevel.LOW)
        thinking_config = types.ThinkingConfig(thinking_level=thinking_level)

    news_tool = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_latest_news",
            description="Fetch a brief summary of current/recent news or facts on a topic. Only call this when the user explicitly asks about recent events, current data, or information that requires up-to-date knowledge beyond your training.",
            parameters=types.Schema(
                type="OBJECT",
                properties={"query": types.Schema(type="STRING", description="Search query")},
                required=["query"],
            ),
        )
    ])

    resumption_handle: Optional[str] = None

    def build_connect_config() -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=settings.gemini.response_modalities,
            speech_config=speech_config,
            thinking_config=thinking_config,
            tools=[news_tool],
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=instruction)]
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=vad_config
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=16000,
                sliding_window=types.SlidingWindow(target_tokens=8000),
            ),
            session_resumption=types.SessionResumptionConfig(
                handle=resumption_handle
            ) if resumption_handle else None,
        )

    connect_config = build_connect_config()
    model_name = settings.gemini.model
    logger.info(f"Connecting to Gemini Live session (model={model_name}, voice={selected_voice}, lang={language})...")

    async def safe_send_json(data: dict):
        if not session_active:
            return
        async with ws_lock:
            try:
                await websocket.send_json(data)
            except Exception:
                pass

    async def safe_send_bytes(data: bytes):
        if not session_active:
            return
        async with ws_lock:
            try:
                await websocket.send_bytes(data)
            except Exception:
                pass

    try:
        async with client.aio.live.connect(model=model_name, config=connect_config) as session:
            logger.info("Connected to Gemini Live session successfully!")
            await safe_send_json({"type": "state", "state": "LISTENING"})

            async def ws_reader():
                """Continuously drains binary PCM16 chunks from the browser WebSocket."""
                nonlocal session_active
                try:
                    while session_active:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            break
                        pcm_bytes = msg.get("bytes")
                        if not pcm_bytes:
                            continue
                        if mic_queue.full():
                            try:
                                mic_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        mic_queue.put_nowait(pcm_bytes)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    pass
                except Exception as e:
                    logger.debug(f"ws_reader ended: {e}")
                finally:
                    session_active = False

            async def mic_to_gemini():
                """Drains mic_queue and transmits realtime input to Gemini Live with minimal latency."""
                nonlocal session_active
                mime_type = "audio/pcm;rate=16000"
                while session_active:
                    try:
                        try:
                            pcm_bytes = await asyncio.wait_for(mic_queue.get(), timeout=0.1)
                        except asyncio.TimeoutError:
                            continue

                        # Batch-drain: send all queued chunks immediately
                        chunks = [pcm_bytes]
                        while not mic_queue.empty():
                            try:
                                chunks.append(mic_queue.get_nowait())
                            except asyncio.QueueEmpty:
                                break

                        combined = b"".join(chunks)
                        blob = types.Blob(data=combined, mime_type=mime_type)
                        await session.send_realtime_input(audio=blob)
                        for _ in chunks:
                            mic_queue.task_done()
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        if session_active:
                            logger.error(f"Gemini send error (ending session): {e}")
                            session_active = False
                            err_msg = "Gemini API Quota Exceeded or Connection Dropped." if "exhausted" in str(e).lower() else "Connection to AI service lost."
                            await safe_send_json({"type": "error", "message": err_msg})
                        break

            async def gemini_to_browser():
                """Receives Gemini Live audio and events across turns and interruptions."""
                nonlocal current_epoch, session_active, resumption_handle
                while session_active:
                    try:
                        async for response in session.receive():
                            if not session_active:
                                break

                            # 0. Session Resumption Handle & Go-Away Signals
                            resump = getattr(response, "session_resumption", None)
                            if resump and getattr(resump, "handle", None):
                                resumption_handle = resump.handle
                                logger.debug(f"Saved session resumption handle: {resumption_handle[:16]}...")

                            go_away = getattr(response, "go_away", None)
                            if go_away:
                                logger.warning(f"Received go_away from Gemini server (time left: {getattr(go_away, 'time_left', 'N/A')}).")

                            # 0.1 Function / Tool Calling Dispatch
                            tool_call = getattr(response, "tool_call", None)
                            if tool_call and getattr(tool_call, "function_calls", None):
                                for fc in tool_call.function_calls:
                                    if fc.name == "get_latest_news":
                                        query_arg = str((fc.args or {}).get("query", ""))
                                        logger.info(f"Executing tool call '{fc.name}' (query: '{query_arg}')")
                                        news_result = await fetch_news_summary(query_arg)
                                        try:
                                            logger.info(f"Sending tool response back to Gemini (id={fc.id})...")
                                            await session.send_tool_response(
                                                function_responses=[
                                                    types.FunctionResponse(
                                                        id=fc.id,
                                                        name=fc.name,
                                                        response={"result": news_result},
                                                    )
                                                ]
                                            )
                                            logger.info(f"Tool response delivered to Gemini for '{fc.name}'.")
                                        except Exception as tool_err:
                                            logger.error(f"Error delivering tool response: {tool_err}", exc_info=True)

                            server_content = response.server_content
                            if server_content is None:
                                continue

                            # 1. Server-Side Barge-In Interruption
                            if getattr(server_content, "interrupted", False):
                                current_epoch += 1
                                logger.info(f"Barge-in triggered by Gemini! Epoch advanced to {current_epoch}.")
                                await safe_send_json({
                                    "type": "barge_in",
                                    "epoch": current_epoch,
                                    "state": "LISTENING"
                                })
                                continue

                            # 2. Incoming Model Audio Chunks
                            model_turn = server_content.model_turn
                            if model_turn:
                                for part in model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        # Prepend 4-byte big-endian epoch header
                                        epoch_header = current_epoch.to_bytes(4, byteorder="big")
                                        await safe_send_bytes(epoch_header + part.inline_data.data)
                                        await safe_send_json({"type": "state", "state": "PLAYING"})

                            # 3. Turn Complete
                            if getattr(server_content, "turn_complete", False):
                                logger.info("Gemini turn completed.")
                                await safe_send_json({"type": "state", "state": "LISTENING"})

                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        if session_active:
                            logger.error(f"Gemini receive error (ending session): {e}")
                            session_active = False
                            err_msg = "Gemini API Quota Exceeded. Please check your API quota or wait a minute." if "exhausted" in str(e).lower() else "AI service connection error."
                            await safe_send_json({"type": "error", "message": err_msg})
                        break

            # Start worker tasks
            reader_task = asyncio.create_task(ws_reader())
            mic_task = asyncio.create_task(mic_to_gemini())
            gemini_task = asyncio.create_task(gemini_to_browser())

            # Only the browser websocket reader closing determines session termination
            await reader_task

            session_active = False
            mic_task.cancel()
            gemini_task.cancel()
            await asyncio.gather(mic_task, gemini_task, return_exceptions=True)

    except WebSocketDisconnect:
        logger.info("Browser client disconnected cleanly.")
    except Exception as e:
        logger.error(f"WebSocket session exception: {e}", exc_info=True)
    finally:
        async with _session_lock:
            _active_sessions = max(0, _active_sessions - 1)
        logger.info(f"Session released [{_active_sessions}/{MAX_CONCURRENT_SESSIONS} sessions]")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("voice_speech.web_server:app", host="0.0.0.0", port=8000, log_level="info")
