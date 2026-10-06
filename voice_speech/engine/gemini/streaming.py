"""Gemini Live Audio Streaming & Bidirectional Pipeline.

Handles low-latency PCM16 audio bridging between browser Web Audio and Gemini Live,
barge-in interruption tracking, tool call execution, and automated session resumption.
"""

import asyncio
import logging
from typing import Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from voice_speech.engine.config.settings import Settings
from voice_speech.engine.conversation.state import ConversationState
from voice_speech.engine.conversation.session_manager import SessionManager
from voice_speech.engine.gemini.session import build_connect_config
from voice_speech.engine.gemini.tools import dispatch_tool_call

logger = logging.getLogger("riva.streaming")


def _build_action_card(tool_name: str, args: dict, status: str = "running", elapsed_ms: int = 0, result: Optional[str] = None) -> Optional[dict]:
    """Builds a structured action_card WebSocket payload for each tool.

    The frontend uses this to dynamically inject floating DOM cards via JavaScript
    showing live tool activity — no HTML/CSS files are modified.

    Args:
        tool_name: Name of the Gemini function being called.
        args: Tool arguments dict.
        status: 'running' (before execution) or 'done' (after completion).
        elapsed_ms: Time taken in ms (only meaningful when status='done').

    Returns:
        dict payload to send via WebSocket, or None if tool needs no card.
    """
    elapsed_str = f"{elapsed_ms / 1000:.1f}s" if elapsed_ms else ""

    if tool_name == "type_in_application":
        app = str(args.get("app_name", "")).lower()
        content = str(args.get("content", ""))
        subject = str(args.get("subject", "Draft from Riva"))
        recipient = str(args.get("recipient", "")).strip()
        preview = content[:120] + ("..." if len(content) > 120 else "")

        if "gmail" in app or "mail" in app or "email" in app:
            import urllib.parse
            encoded_sub = urllib.parse.quote(subject)
            encoded_body = urllib.parse.quote(content)
            encoded_to = urllib.parse.quote(recipient) if recipient else ""
            compose_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={encoded_to}&su={encoded_sub}&body={encoded_body}"
            return {
                "type": "action_card",
                "tool": tool_name,
                "icon": "📧",
                "title": "Gmail — Composing Email" if status == "running" else f"✅ Email Opened in Gmail ({elapsed_str})",
                "subject": subject,
                "recipient": recipient,
                "preview": preview,
                "url": compose_url,
                "status": status,
            }
        else:
            return {
                "type": "action_card",
                "tool": tool_name,
                "icon": "📝",
                "title": "Notepad — Live Typing" if status == "running" else f"✅ Typed in Notepad ({elapsed_str})",
                "preview": preview,
                "status": status,
            }

    elif tool_name == "open_application":
        target = str(args.get("target", "")).strip()
        icons = {
            "camera": "📷", "webcam": "📷", "gmail": "📧", "mail": "📧",
            "notepad": "📝", "calc": "🧮", "calculator": "🧮",
            "youtube": "▶️", "spotify": "🎵", "chrome": "🌐",
            "browser": "🌐", "google": "🌐", "github": "🐱",
            "whatsapp": "💬", "settings": "⚙️", "leetcode": "💻",
            "chatgpt": "🤖",
        }
        icon = icons.get(target.lower(), "🖥️")
        
        resolved_url = None
        if "leetcode" in target.lower():
            if "random" in target.lower():
                resolved_url = "https://leetcode.com/problems/random-one-question/all"
            else:
                resolved_url = "https://leetcode.com/problemset/"
            icon = "💻"
        elif target.lower() in ("gmail", "mail", "email"):
            resolved_url = "https://mail.google.com"
        elif target.lower() == "irctc":
            resolved_url = "https://www.irctc.co.in"
            icon = "🚆"
        elif target.lower() == "youtube":
            resolved_url = "https://www.youtube.com"
        elif target.lower() == "github":
            resolved_url = "https://github.com"
        elif target.lower() in ("chatgpt", "openai"):
            resolved_url = "https://chatgpt.com"
        elif target.startswith(("http://", "https://")):
            resolved_url = target
        elif "." in target and not target.endswith((".exe", ".bat", ".cmd", ".ps1")):
            resolved_url = "https://" + target

        card = {
            "type": "action_card",
            "tool": tool_name,
            "icon": icon,
            "title": f"Opening {target.title()}..." if status == "running" else f"✅ {target.title()} Opened ({elapsed_str})",
            "status": status,
        }
        if resolved_url:
            card["url"] = resolved_url
        return card

    elif tool_name == "capture_photo":
        return {
            "type": "action_card",
            "tool": tool_name,
            "icon": "📸",
            "title": "Capturing photo from webcam..." if status == "running" else f"✅ Photo Captured & Saved ({elapsed_str})",
            "status": status,
        }

    elif tool_name == "delegate_to_orchestrator":
        task = str(args.get("task_prompt", ""))
        preview = task[:100] + ("..." if len(task) > 100 else "")
        return {
            "type": "action_card",
            "tool": tool_name,
            "icon": "🤖",
            "title": "Multi-Agent Orchestrator Running..." if status == "running" else f"✅ Task Complete ({elapsed_str})",
            "preview": preview,
            "status": status,
        }

    elif tool_name == "inspect_browser_tab":
        target = str(args.get("target", "active")).strip()
        icon = "💻" if "leetcode" in target.lower() else ("📧" if "gmail" in target.lower() else "🔍")
        url_map = {
            "leetcode": "https://leetcode.com/problems/random-one-question/all",
            "gmail": "https://mail.google.com",
            "mail": "https://mail.google.com",
            "github": "https://github.com",
        }
        card = {
            "type": "action_card",
            "tool": tool_name,
            "icon": icon,
            "title": f"Inspecting {target.title()} DOM..." if status == "running" else f"✅ {target.title()} Context Extracted ({elapsed_str})",
            "status": status,
            "target": target,
        }
        if target.lower() in url_map:
            card["url"] = url_map[target.lower()]
        if result:
            card["result"] = result
            card["preview"] = result[:250] + ("..." if len(result) > 250 else "")
        return card

    elif tool_name == "get_latest_news":
        query = str(args.get("query", ""))
        return {
            "type": "action_card",
            "tool": tool_name,
            "icon": "🌐",
            "title": f'Searching: "{query[:60]}"' if status == "running" else f"✅ Search Complete ({elapsed_str})",
            "status": status,
        }

    elif tool_name == "send_current_draft":
        return {
            "type": "action_card",
            "tool": tool_name,
            "icon": "🚀",
            "title": "Sending Email Draft..." if status == "running" else f"✅ Email Sent Successfully ({elapsed_str})",
            "preview": "Triggered Send button in Gmail window.",
            "status": status,
        }

    return None


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
            if state.is_tool_running:
                await asyncio.sleep(0.05)
                continue

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

            if state.is_tool_running:
                for _ in chunks:
                    state.mic_queue.task_done()
                continue

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
                if _is_quota_error(e):
                    session_mgr.trip_circuit_breaker()
                    state.terminate()
                    await state.safe_send_json(
                        websocket,
                        {"type": "error", "message": f"Gemini API Quota Exceeded. Please wait ~{int(session_mgr.cooldown_seconds)}s before retrying."}
                    )
            break


def _is_quota_error(err: Any) -> bool:
    """Returns True only for genuine upstream quota exhaustion or rate limits."""
    s = str(err).lower()
    return "quota" in s or "resource_exhausted" in s or "429" in s


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
                resump = getattr(response, "session_resumption_update", None) or getattr(response, "session_resumption", None)
                if resump:
                    handle = getattr(resump, "new_handle", None) or getattr(resump, "handle", None)
                    if handle:
                        state.resumption_handle = handle
                        logger.debug(f"Saved session resumption handle: {state.resumption_handle[:16]}...")

                go_away = getattr(response, "go_away", None)
                if go_away:
                    time_left = getattr(go_away, "time_left", "N/A")
                    logger.warning(f"Received go_away from Gemini server (time left: {time_left}). Resuming session...")
                    return  # Exit cleanly so outer loop reconnects with resumption_handle

                # 1. Tool Calling Dispatch via Extensible Registry
                tool_call = getattr(response, "tool_call", None)
                if tool_call and getattr(tool_call, "function_calls", None):
                    state.is_tool_running = True
                    # Immediately notify frontend — UI can show a spinner/animation
                    # instead of a frozen silent interface during long tasks
                    await state.safe_send_json(
                        websocket,
                        {"type": "state", "state": "PROCESSING"}
                    )
                    try:
                        import time as _time
                        function_responses = []
                        for fc in tool_call.function_calls:
                            # Send action_card BEFORE tool runs so DOM panel appears instantly
                            action_card = _build_action_card(fc.name, fc.args or {}, status="running")
                            if action_card:
                                await state.safe_send_json(websocket, action_card)
                                logger.info(f"Sent action_card [running] for '{fc.name}'")

                            t0 = _time.monotonic()
                            result_str = await dispatch_tool_call(fc.name, fc.args or {})
                            elapsed_ms = round((_time.monotonic() - t0) * 1000)
                            logger.info(f"Tool '{fc.name}' completed in {elapsed_ms}ms.")

                            # Send done update so DOM card shows completion
                            if action_card:
                                done_card = _build_action_card(fc.name, fc.args or {}, status="done", elapsed_ms=elapsed_ms, result=result_str)
                                if done_card:
                                    await state.safe_send_json(websocket, done_card)

                            function_responses.append(
                                types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result_str})
                            )
                        if function_responses:
                            await session.send_tool_response(function_responses=function_responses)
                            logger.info(f"Delivered {len(function_responses)} tool response(s) to Gemini.")
                    except Exception as tool_err:
                        logger.error(f"Error delivering tool response: {tool_err}", exc_info=True)
                    finally:
                        state.is_tool_running = False

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
            state.resumption_handle = None  # Clear invalid resumption handle on crash
            if state.session_active:
                logger.error(f"Gemini receive error: {e}")
                if _is_quota_error(e):
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
                state.resumption_handle = None
                if not state.session_active:
                    break
                if _is_quota_error(conn_err):
                    session_mgr.trip_circuit_breaker()
                    state.terminate()
                    await state.safe_send_json(
                        websocket,
                        {"type": "error", "message": f"Gemini API Quota Exceeded. Please wait ~{int(session_mgr.cooldown_seconds)}s before retrying."}
                    )
                    break

                if state.session_active:
                    logger.warning(f"Gemini connection interrupted: {conn_err}. Reconnecting in 0.5s...")
                    await asyncio.sleep(0.5)


            if state.resumption_handle and state.session_active:
                logger.info("Gemini session finished turn. Resuming session in 0.5s...")
                await asyncio.sleep(0.5)

    finally:
        state.terminate()
        reader_task.cancel()
        await asyncio.gather(reader_task, return_exceptions=True)
