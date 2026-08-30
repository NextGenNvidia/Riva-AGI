"""Gemini Live Audio Streaming & Bidirectional Pipeline.

Handles low-latency PCM16 audio bridging between browser Web Audio and Gemini Live,
barge-in interruption tracking, tool call execution, and automated session resumption.
"""

import asyncio
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from voice_speech.engine.config.settings import Settings
from voice_speech.engine.conversation.state import ConversationState
from voice_speech.engine.conversation.session_manager import SessionManager
from voice_speech.engine.gemini.session import build_connect_config
from voice_speech.engine.gemini.tools import dispatch_tool_call

logger = logging.getLogger("riva.streaming")


async def ws_reader(websocket: WebSocket, state: ConversationState) -> None:
    """Continuously drains binary PCM16 audio chunks from the client WebSocket into the mic queue."""
    try:
        while state.session_active:
            msg = await websocket.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            pcm_bytes = msg.get("bytes")
            if not pcm_bytes:
                continue
            if state.mic_queue.full():
                try:
                    state.mic_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            state.mic_queue.put_nowait(pcm_bytes)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.debug(f"ws_reader ended: {e}")
    finally:
        state.terminate()


async def mic_to_gemini(
    session,
    state: ConversationState,
    session_mgr: SessionManager,
    websocket: WebSocket,
) -> None:
    """Transmits microphone audio chunks from the mic queue to Gemini Live in real time."""
    mime_type = "audio/pcm;rate=16000"
    while state.session_active:
        try:
            try:
                pcm_bytes = await asyncio.wait_for(state.mic_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            # Batch-drain all pending chunks for minimal latency
            chunks = [pcm_bytes]
            while not state.mic_queue.empty():
                try:
                    chunks.append(state.mic_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break

            combined = b"".join(chunks)
            blob = types.Blob(data=combined, mime_type=mime_type)
            await session.send_realtime_input(audio=blob)
            for _ in chunks:
                state.mic_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            if state.session_active:
                logger.error(f"Gemini mic transmit error: {e}")
                if "exhausted" in str(e).lower() or "1011" in str(e):
                    session_mgr.trip_circuit_breaker()
                    state.terminate()
                    await state.safe_send_json(
                        websocket,
                        {"type": "error", "message": f"Gemini API Quota Exceeded. Please wait ~{int(session_mgr.cooldown_seconds)}s before retrying."}
                    )
            break


async def gemini_to_browser(
    session,
    state: ConversationState,
    session_mgr: SessionManager,
    websocket: WebSocket,
) -> None:
    """Receives model audio chunks, barge-in interruptions, and tool calls from Gemini Live."""
    while state.session_active:
        try:
            async for response in session.receive():
                if not state.session_active:
                    break

                # 0. Session Resumption Handle & Go-Away Signals
                resump = getattr(response, "session_resumption", None)
                if resump and getattr(resump, "handle", None):
                    state.resumption_handle = resump.handle
                    logger.debug(f"Saved session resumption handle: {state.resumption_handle[:16]}...")

                go_away = getattr(response, "go_away", None)
                if go_away:
                    time_left = getattr(go_away, "time_left", "N/A")
                    logger.warning(f"Received go_away from Gemini server (time left: {time_left}). Resuming session...")
                    return  # Exit cleanly so outer loop reconnects with resumption_handle

                # 1. Tool Calling Dispatch via Extensible Registry
                tool_call = getattr(response, "tool_call", None)
                if tool_call and getattr(tool_call, "function_calls", None):
                    function_responses = []
                    for fc in tool_call.function_calls:
                        result_str = await dispatch_tool_call(fc.name, fc.args or {})
                        function_responses.append(
                            types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str})
                        )
                    if function_responses:
                        try:
                            await session.send_tool_response(function_responses=function_responses)
                            logger.info(f"Delivered {len(function_responses)} tool response(s) to Gemini.")
                        except Exception as tool_err:
                            logger.error(f"Error delivering tool response: {tool_err}", exc_info=True)

                server_content = response.server_content
                if server_content is None:
                    continue

                # 2. Server-Side Barge-In Interruption
                if getattr(server_content, "interrupted", False):
                    new_epoch = state.advance_epoch()
                    logger.info(f"Barge-in triggered by Gemini! Epoch advanced to {new_epoch}.")
                    await state.safe_send_json(
                        websocket,
                        {"type": "barge_in", "epoch": new_epoch, "state": "LISTENING"}
                    )
                    continue

                # 3. Incoming Model Audio Chunks
                model_turn = server_content.model_turn
                if model_turn:
                    for part in model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            epoch_header = state.current_epoch.to_bytes(4, byteorder="big")
                            await state.safe_send_bytes(websocket, epoch_header + part.inline_data.data)
                            await state.safe_send_json(websocket, {"type": "state", "state": "PLAYING"})

                # 4. Turn Complete
                if getattr(server_content, "turn_complete", False):
                    logger.info("Gemini turn completed.")
                    await state.safe_send_json(websocket, {"type": "state", "state": "LISTENING"})

        except asyncio.CancelledError:
            break
        except Exception as e:
            if state.session_active:
                logger.error(f"Gemini receive error: {e}")
                if "exhausted" in str(e).lower() or "1011" in str(e):
                    session_mgr.trip_circuit_breaker()
                    state.terminate()
                    await state.safe_send_json(
                        websocket,
                        {"type": "error", "message": f"Gemini API Quota Exceeded. Please wait ~{int(session_mgr.cooldown_seconds)}s before retrying."}
                    )
            break


async def run_live_bridge(
    client,
    websocket: WebSocket,
    settings: Settings,
    state: ConversationState,
    session_mgr: SessionManager,
    voice: str = "Aoede",
    language: str = "auto",
) -> None:
    """Runs the persistent bidirectional bridge with automated session resumption reconnects."""
    model_name = settings.gemini.model
    reader_task = asyncio.create_task(ws_reader(websocket, state))

    try:
        while state.session_active:
            # Check circuit breaker before each reconnect attempt
            is_open, remaining = session_mgr.is_circuit_open()
            if is_open:
                logger.warning(f"Active quota cooldown in progress ({remaining}s). Aborting session bridge.")
                state.terminate()
                break

            connect_config = build_connect_config(
                settings=settings,
                voice=voice,
                language=language,
                resumption_handle=state.resumption_handle,
            )
            is_resumed = bool(state.resumption_handle)
            logger.info(f"Connecting to Gemini Live (model={model_name}, voice={voice}, resumed={is_resumed})...")

            try:
                async with client.aio.live.connect(model=model_name, config=connect_config) as session:
                    logger.info("Connected to Gemini Live session successfully!")
                    await state.safe_send_json(websocket, {"type": "state", "state": "LISTENING"})

                    mic_task = asyncio.create_task(mic_to_gemini(session, state, session_mgr, websocket))
                    gemini_task = asyncio.create_task(gemini_to_browser(session, state, session_mgr, websocket))

                    done, pending = await asyncio.wait(
                        [mic_task, gemini_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)

            except Exception as conn_err:
                if not state.session_active:
                    break
                if "exhausted" in str(conn_err).lower() or "1011" in str(conn_err):
                    session_mgr.trip_circuit_breaker()
                    state.terminate()
                    await state.safe_send_json(
                        websocket,
                        {"type": "error", "message": f"Gemini API Quota Exceeded. Please wait ~{int(session_mgr.cooldown_seconds)}s before retrying."}
                    )
                    break

                if state.resumption_handle and state.session_active:
                    logger.info("Gemini session ended. Resuming session seamlessly in 0.5s...")
                    await asyncio.sleep(0.5)
                else:
                    logger.warning(f"Gemini connection error: {conn_err}")
                    break

            if state.resumption_handle and state.session_active:
                logger.info("Gemini session finished turn. Resuming session in 0.5s...")
                await asyncio.sleep(0.5)

    finally:
        state.terminate()
        reader_task.cancel()
        await asyncio.gather(reader_task, return_exceptions=True)
