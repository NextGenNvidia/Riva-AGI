"""
Riva WebRTC Gateway Server (FastAPI + WebSocket).
Persistent, non-disconnecting bridge between browser WebRTC and Gemini Live API.
"""

import asyncio
import logging
import os
import sys
import time
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

# Pre-warmed Gemini client singleton
genai_client = genai.Client(api_key=settings.gemini.api_key)

app = FastAPI(title="Riva WebRTC Gateway")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")


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
    await websocket.accept()

    # Read voice and language directly from query parameters
    voice = websocket.query_params.get("voice") or "Aoede"
    language = websocket.query_params.get("language") or "auto"
    logger.info(f"Browser WebRTC client connected to /ws (voice={voice}, language={language})")

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

    connect_config = types.LiveConnectConfig(
        response_modalities=settings.gemini.response_modalities,
        speech_config=speech_config,
        thinking_config=thinking_config,
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=instruction)]
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=vad_config
        ),
    )

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
                nonlocal current_epoch, session_active
                while session_active:
                    try:
                        async for response in session.receive():
                            if not session_active:
                                break

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("voice_speech.web_server:app", host="0.0.0.0", port=8000, log_level="info")
