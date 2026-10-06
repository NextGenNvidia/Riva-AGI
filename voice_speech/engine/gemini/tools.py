"""Gemini Live Function Calling Tools & Registry.

Provides zero-key real-time news retrieval (Google News RSS + NewsAPI fallback)
and an extensible dispatcher registry for tool calls.
"""

import asyncio
import json
import logging
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Awaitable, Callable, Dict, List
from google.genai import types

logger = logging.getLogger("riva.tools")


async def fetch_news_summary(query: str) -> str:
    """Fetches real-time web news, facts, and live context using Tavily Search (if key provided),

    NewsAPI (fallback), or universal Google News RSS (zero-key fallback).
    """
    clean_query = query.strip()
    if not clean_query:
        clean_query = "top world news"

    tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
    news_api_key = os.getenv("NEWS_API_KEY", "").strip()
    loop = asyncio.get_running_loop()

    # 1. Primary: Tavily AI Search (rich context, snippets, and answers if key provided)
    if tavily_api_key:
        try:
            payload = {
                "api_key": tavily_api_key,
                "query": clean_query,
                "search_depth": "basic",
                "max_results": 4,
                "include_answer": True,
            }
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "RivaVoice/1.0"},
                method="POST",
            )

            def _fetch_tavily():
                with urllib.request.urlopen(req, timeout=4.5) as resp:
                    return resp.read()

            raw_bytes = await loop.run_in_executor(None, _fetch_tavily)
            data = json.loads(raw_bytes.decode("utf-8"))

            snippets = []
            answer = data.get("answer")
            if answer:
                snippets.append(f"Direct Answer: {answer}")

            for item in data.get("results", [])[:4]:
                title = item.get("title", "").strip()
                content = item.get("content", "").strip()
                if title and content:
                    snippets.append(f"{title}: {content}")
                elif title:
                    snippets.append(title)

            if snippets:
                summary = " | ".join(snippets)[:1400]
                logger.info(f"Live Tavily response for '{clean_query}': {summary[:120]!r}")
                return summary
        except Exception as e:
            logger.warning(f"Tavily search error (falling back to NewsAPI / Google News): {e}")

    # 2. Secondary: NewsAPI.org query (if key provided)
    if news_api_key:
        try:
            encoded = urllib.parse.quote(clean_query)
            url = f"https://newsapi.org/v2/everything?q={encoded}&pageSize=4&sortBy=publishedAt&apiKey={news_api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "RivaVoice/1.0"})

            def _fetch_newsapi():
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    return resp.read()

            raw_json = await loop.run_in_executor(None, _fetch_newsapi)
            data = json.loads(raw_json)
            articles = data.get("articles", [])
            items = []
            for a in articles[:4]:
                title = a.get("title", "").strip()
                desc = a.get("description", "").strip()
                if title and desc:
                    items.append(f"{title} - {desc}")
                elif title:
                    items.append(title)
            if items:
                summary = " | ".join(items)[:1000]
                logger.info(f"Live NewsAPI response for '{clean_query}': {summary[:120]!r}")
                return summary
        except Exception as e:
            logger.warning(f"NewsAPI error (falling back to Google News RSS): {e}")

    # 3. Universal Zero-Key Fallback: Google News RSS
    try:
        encoded = urllib.parse.quote(clean_query)
        url = f"https://news.google.com/rss/search?q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

        def _fetch_rss():
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return resp.read()

        xml_data = await loop.run_in_executor(None, _fetch_rss)
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")

        headlines = []
        for item in items[:8]:
            title = item.find("title")
            if title is not None and title.text:
                # Strip trailing publisher tag while preserving internal hyphens in scores & stats
                clean_title = title.text.rsplit(" - ", 1)[0].strip() if " - " in title.text else title.text.strip()
                if clean_title and clean_title not in headlines:
                    headlines.append(clean_title)

        if headlines:
            summary = " | ".join(headlines)[:1000]
            logger.info(f"Live News RSS response for '{clean_query}': {summary[:120]!r}")
            return summary

        return f"No recent breaking news found for '{clean_query}'."
    except Exception as e:
        logger.warning(f"News RSS fetch error for '{clean_query}': {e}")
        return f"Could not retrieve recent news for '{clean_query}'."


# Tool Declarations
NEWS_TOOL_DECLARATION = types.FunctionDeclaration(
    name="get_latest_news",
    description=(
        "Search real-time web news, current events, recent developments, facts, or live updates on any topic. "
        "Call this tool whenever the user asks about current affairs, breaking news, recent events, "
        "people, organizations, technology, culture, weather, statistics, or any topic requiring fresh or up-to-date information."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={"query": types.Schema(type="STRING", description="Search query keywords or topic to look up")},
        required=["query"],
    ),
    
)

ORCHESTRATOR_TOOL_DECLARATION = types.FunctionDeclaration(
    name="delegate_to_orchestrator",
    description=(
        "Delegate any software development task, multi-file project creation, standalone script implementation, "
        "automated test execution, deep technical research, or multi-agent execution to the Riva Multi-Agent Orchestrator backend. "
        "CRITICAL: Whenever the user asks to build a project, write a program/script, or perform technical research, "
        "do not recite code blocks verbally. Delegate the task by calling this tool."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "task_prompt": types.Schema(
                type="STRING",
                description="The exact user instruction or task to execute."
            )
        },
        required=["task_prompt"],
    ),
)

OPEN_APPLICATION_TOOL_DECLARATION = types.FunctionDeclaration(
    name="open_application",
    description=(
        "Open any desktop application (such as Notepad, Calculator, Camera, Paint, Terminal, File Explorer) "
        "or navigate to any website, web application, or URL (e.g. any domain, https:// URL, Google, GitHub, LeetCode, YouTube) "
        "on the user's computer."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "target": types.Schema(
                type="STRING",
                description="The application name (e.g. 'notepad', 'calc', 'camera') or website/URL (e.g. 'https://...', 'github', 'leetcode', 'gmail')."
            )
        },
        required=["target"],
    ),
)

CAPTURE_PHOTO_TOOL_DECLARATION = types.FunctionDeclaration(
    name="capture_photo",
    description=(
        "Capture a photo directly from the connected webcam or camera, save it as an image file on disk, and display it on the user's screen. "
        "Call this whenever the user asks to capture an image, take a photo, or snap a picture."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "filename": types.Schema(
                type="STRING",
                description="Optional filename for the photo (defaults to 'captured_photo.jpg')."
            )
        },
    ),
)

TYPE_IN_APPLICATION_TOOL_DECLARATION = types.FunctionDeclaration(
    name="type_in_application",
    description=(
        "Open a desktop application or web interface (such as Notepad, Gmail, LinkedIn, or Twitter) and compose notes, essays, emails, or social media posts directly onto the screen. "
        "Call this whenever the user asks to compose a note, write an essay, draft an email, or prepare a social media post."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "app_name": types.Schema(
                type="STRING",
                description="The target application to compose in, e.g. 'notepad', 'gmail', 'linkedin', or 'twitter'."
            ),
            "content": types.Schema(
                type="STRING",
                description="The full content, essay, body, or text to compose and type."
            ),
            "subject": types.Schema(
                type="STRING",
                description="Optional email subject line if drafting an email."
            ),
            "recipient": types.Schema(
                type="STRING",
                description="Optional recipient email address if drafting an email."
            ),
            "auto_send": types.Schema(
                type="BOOLEAN",
                description="Optional. If true, automatically sends the email immediately after composing."
            ),
        },
        required=["app_name", "content"],
    ),
)

INSPECT_BROWSER_TAB_DECLARATION = types.FunctionDeclaration(
    name="inspect_browser_tab",
    description=(
        "Inspect the semantic DOM content of any active browser tab, web application, or URL. "
        "Extracts headings, visible content, code editor text, or inbox state across any website, developer platform, or web application. "
        "Call this whenever the user asks to inspect, check, or review the screen, code editor, or open web page."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "target": types.Schema(
                type="STRING",
                description="The target site, domain, or application to inspect, e.g. 'active', 'leetcode', 'gmail', 'github', or any URL."
            )
        },
        required=["target"],
    ),
)

SEND_CURRENT_DRAFT_DECLARATION = types.FunctionDeclaration(
    name="send_current_draft",
    description=(
        "Send the active email draft or message in the browser by clicking the Send button or triggering the Ctrl+Enter keyboard shortcut. "
        "Call this whenever the user confirms sending an email or draft message."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "target": types.Schema(
                type="STRING",
                description="The target application or window, e.g. 'gmail'."
            )
        },
    ),
)

WRITE_CODE_IN_BROWSER_DECLARATION = types.FunctionDeclaration(
    name="write_code_in_browser",
    description=(
        "Stream and type code visibly into the active web code editor (such as Monaco editor, LeetCode, or online IDEs) "
        "with real-time typing animation and cursor tracking, followed by executing test cases on screen. "
        "Call this whenever the user asks to type code or insert a solution into the browser editor."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "code": types.Schema(
                type="STRING",
                description="The complete solution code to type into the editor."
            ),
            "target": types.Schema(
                type="STRING",
                description="The target site or application, default 'leetcode'."
            ),
            "auto_run": types.Schema(
                type="BOOLEAN",
                description="Whether to automatically run test cases after typing (default: true)."
            ),
            "auto_submit": types.Schema(
                type="BOOLEAN",
                description="Whether to automatically submit the solution if tests pass (default: false)."
            ),
        },
        required=["code"],
    ),
)

NEXT_LEETCODE_QUESTION_DECLARATION = types.FunctionDeclaration(
    name="next_leetcode_question",
    description=(
        "Navigate the browser to a new random coding problem or question in the active coding session. "
        "Call this whenever the user asks to change the problem or load the next question."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)

SOLVE_LEETCODE_PROBLEM_DECLARATION = types.FunctionDeclaration(
    name="solve_leetcode_problem",
    description=(
        "Autonomously solve the active coding problem displayed in the browser. "
        "Inspects problem specifications, generates the optimal algorithmic solution, "
        "streams the code into the editor, and triggers test execution on screen. "
        "Call this whenever the user asks to solve the coding problem displayed in the browser."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "pick_random": types.Schema(
                type="BOOLEAN",
                description="Whether to pick a new random problem before solving (default: false)."
            ),
            "auto_run": types.Schema(
                type="BOOLEAN",
                description="Whether to run the test cases on screen after typing (default: true)."
            ),
            "auto_submit": types.Schema(
                type="BOOLEAN",
                description="Whether to submit the solution if test cases pass (default: false)."
            ),
        },
    ),
)

DEFAULT_TOOLS: List[types.Tool] = [
    types.Tool(function_declarations=[
        NEWS_TOOL_DECLARATION,
        ORCHESTRATOR_TOOL_DECLARATION,
        OPEN_APPLICATION_TOOL_DECLARATION,
        CAPTURE_PHOTO_TOOL_DECLARATION,
        TYPE_IN_APPLICATION_TOOL_DECLARATION,
        INSPECT_BROWSER_TAB_DECLARATION,
        SEND_CURRENT_DRAFT_DECLARATION,
        WRITE_CODE_IN_BROWSER_DECLARATION,
        NEXT_LEETCODE_QUESTION_DECLARATION,
        SOLVE_LEETCODE_PROBLEM_DECLARATION,
    ])
]


async def _handle_get_latest_news(args: Dict[str, Any]) -> str:
    query = str((args or {}).get("query", ""))
    return await fetch_news_summary(query)


async def _handle_delegate_to_orchestrator(args: Dict[str, Any]) -> str:
    prompt = str((args or {}).get("task_prompt", "")).strip()
    if not prompt:
        return "No task prompt provided for orchestrator."

    loop = asyncio.get_running_loop()

    # ── Spoken acknowledgment ─────────────────────────────────────────────────
    # Immediately log so Gemini can speak a warm acknowledgment WHILE the heavy
    # orchestrator pipeline runs in the background executor thread.
    logger.info(f"[Orchestrator] Task queued: {prompt[:80]}...")

    def _run_orch():
        from orchestration.orchestrator.main import run_orchestrator
        t0 = __import__("time").time()
        res = run_orchestrator(task_text=prompt, source="voice_gateway")
        elapsed_s = round(__import__("time").time() - t0, 1)
        payload = res.get("response_payload")
        plan = res.get("plan", [])
        completed = res.get("completed_steps", [])

        # Persist complete deliverable to docs/last_deliverable.md
        if payload and payload.content:
            deliv_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "last_deliverable.md")
            )
            try:
                os.makedirs(os.path.dirname(deliv_path), exist_ok=True)
                with open(deliv_path, "w", encoding="utf-8") as f:
                    f.write(payload.content)
                logger.info(f"Persisted complete deliverable to {deliv_path}")
            except Exception as fe:
                logger.warning(f"Could not write deliverable to disk: {fe}")

        task_count = len(plan) if plan else (len(completed) or 1)

        # Check if files were created on disk by tool calls
        created_files = []
        if payload and payload.tool_calls:
            for tc in payload.tool_calls:
                fp = tc.parameters.get("file_path")
                if fp:
                    created_files.append(fp)

        if created_files:
            file_names = ", ".join(os.path.basename(fp) for fp in created_files)
            return (
                f"Done! Completed in {elapsed_s}s. "
                f"Created {file_names} in your workspace. All tests passed."
            )

        return (
            f"Done! Completed {task_count} subtasks in {elapsed_s}s. "
            f"The task has been fully executed by the multi-agent pipeline."
        )

    return await loop.run_in_executor(None, _run_orch)


def _launch_browser_url(url: str) -> bool:
    """Launches a web URL in the user's primary desktop browser (Microsoft Edge) on Windows.

    Checks for Microsoft Edge first so that user sessions active in Edge open directly
    in their active browser. Enables remote debugging port 9222.
    Falls back gracefully to Google Chrome, os.startfile, webbrowser.open, and shell execution.
    """
    import subprocess
    import shutil
    import os

    # 1. Prioritize Microsoft Edge (the active browser for the user session)
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
    ]
    which_edge = shutil.which("msedge")
    if which_edge:
        edge_candidates.insert(0, which_edge)

    # 2. Chrome fallback candidates
    chrome_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
    ]
    which_chrome = shutil.which("chrome")
    if which_chrome:
        chrome_candidates.insert(0, which_chrome)

    browser_candidates = edge_candidates + chrome_candidates

    # 1. Prioritize opening in user's default browser session (where Gmail, accounts are already logged in)
    try:
        os.startfile(url)
        logger.info(f"Launched URL in user's default logged-in browser via os.startfile: {url}")
        return True
    except Exception as e:
        logger.debug(f"os.startfile failed: {e}")

    # 2. Directly open in Microsoft Edge without isolating user data dir (uses default profile)
    for exe in edge_candidates + chrome_candidates:
        if exe and os.path.exists(exe):
            try:
                subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info(f"Launched URL in default browser profile: {url} via {exe}")
                return True
            except Exception as e:
                logger.warning(f"Could not launch browser at {exe}: {e}")

    # 3. Try Python webbrowser module
    try:
        import webbrowser
        webbrowser.open(url)
        logger.info(f"Launched URL via webbrowser.open: {url}")
        return True
    except Exception as e:
        logger.warning(f"webbrowser.open failed for {url}: {e}")

    # 4. Fallback cmd start
    try:
        subprocess.Popen(["cmd", "/c", "start", "", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info(f"Launched URL via cmd start: {url}")
        return True
    except Exception as e:
        logger.error(f"cmd start failed for {url}: {e}")
        return False


async def _handle_open_application(args: Dict[str, Any]) -> str:
    target = str((args or {}).get("target", "")).strip().lower()
    if not target:
        return "No application or target specified to open."

    app_map = {
        "notepad": "notepad.exe",
        "calc": "calc.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "cmd": "cmd.exe",
        "terminal": "powershell.exe",
        "powershell": "powershell.exe",
        "explorer": "explorer.exe",
        "files": "explorer.exe",
        "camera": "microsoft.windows.camera:",
        "webcam": "microsoft.windows.camera:",
        "settings": "ms-settings:",
        "store": "ms-windows-store:",
        "spotify": "spotify:",
        "whatsapp": "whatsapp:",
        "code": "code",
        "vscode": "code",
        "chrome": "https://www.google.com",
        "edge": "https://www.google.com",
        "browser": "https://www.google.com",
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "mail": "https://mail.google.com",
        "email": "https://mail.google.com",
        "youtube": "https://www.youtube.com",
        "github": "https://github.com",
        "leetcode": "https://leetcode.com/problemset/",
        "irctc": "https://www.irctc.co.in",
        "chatgpt": "https://chatgpt.com",
        "openai": "https://chatgpt.com",
    }

    if "leetcode" in target:
        if "random" in target:
            resolved = "https://leetcode.com/problems/random-one-question/all"
        else:
            resolved = "https://leetcode.com/problemset/"
    elif "irctc" in target:
        resolved = "https://www.irctc.co.in"
    elif target in app_map:
        resolved = app_map[target]
    elif target.startswith(("http://", "https://", "microsoft.windows.camera:", "ms-settings:", "microsoft-edge:", "spotify:", "whatsapp:")):
        resolved = target
    elif "." in target and not target.endswith((".exe", ".bat", ".cmd", ".ps1")):
        resolved = "https://" + target
    else:
        resolved = target

    loop = asyncio.get_running_loop()

    def _open_sync():
        try:
            if os.name != "nt":
                return "Desktop application launching is only supported on Windows."

            import subprocess

            is_protocol_or_url = (
                resolved.startswith("http://")
                or resolved.startswith("https://")
                or resolved.startswith("microsoft.windows.camera:")
                or resolved.startswith("ms-settings:")
                or resolved.startswith("microsoft-edge:")
                or resolved.startswith("spotify:")
                or resolved.startswith("whatsapp:")
            )

            if is_protocol_or_url:
                if resolved.startswith(("http://", "https://")):
                    _launch_browser_url(resolved)
                else:
                    # Windows URI schemes: ms-settings:, microsoft.windows.camera:, etc.
                    try:
                        os.startfile(resolved)
                        logger.info(f"Launched URI '{target}' via os.startfile ({resolved})")
                    except Exception as e1:
                        logger.warning(f"os.startfile failed for {resolved}: {e1}")
                        subprocess.Popen(["cmd", "/c", "start", "", resolved], shell=False)

                return f"Opened {target} successfully."
            else:
                # Plain executables: notepad.exe, calc.exe, etc.
                try:
                    os.startfile(resolved)
                    logger.info(f"Launched '{target}' via os.startfile ({resolved})")
                    return f"Opened {target} successfully."
                except Exception:
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", resolved],
                        shell=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return f"Opened {target} successfully."
        except Exception as e:
            logger.error(f"Failed to open {target}: {e}")
            return f"Could not open {target}: {e}"

    return await loop.run_in_executor(None, _open_sync)


async def _handle_capture_photo(args: Dict[str, Any]) -> str:
    filename = str((args or {}).get("filename", "")).strip() or "captured_photo.jpg"
    if not filename.endswith((".jpg", ".png", ".jpeg")):
        filename += ".jpg"

    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    out_path = os.path.join(workspace_dir, filename)

    loop = asyncio.get_running_loop()

    def _snap():
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return "Camera device could not be opened. Please check permissions."

            # Allow camera auto-exposure to calibrate
            for _ in range(5):
                cap.read()
            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                cv2.imwrite(out_path, frame)
                try:
                    if os.name == "nt":
                        os.startfile(out_path)
                except Exception:
                    pass
                return f"Successfully clicked photo and saved to {filename} in your workspace."
            else:
                return "Failed to capture image frame from camera."
        except Exception as e:
            logger.error(f"Error capturing photo: {e}")
            return f"Could not capture photo: {e}"

    return await loop.run_in_executor(None, _snap)


async def _handle_type_in_application(args: Dict[str, Any]) -> str:
    app_name = str((args or {}).get("app_name", "")).strip().lower()
    content = str((args or {}).get("content", "")).strip()
    subject = str((args or {}).get("subject", "")).strip()
    recipient = str((args or {}).get("recipient", "")).strip()
    auto_send = bool((args or {}).get("auto_send", False))
    if not content:
        return "No text content provided to type."

    loop = asyncio.get_running_loop()

    def _type_sync():
        try:
            if "gmail" in app_name or "mail" in app_name or "email" in app_name:
                import urllib.parse
                clean_sub = subject or "Draft from Riva"
                encoded_sub = urllib.parse.quote(clean_sub)
                encoded_body = urllib.parse.quote(content)
                encoded_to = urllib.parse.quote(recipient) if recipient else ""
                compose_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={encoded_to}&su={encoded_sub}&body={encoded_body}"
                
                _launch_browser_url(compose_url)
                logger.info(f"Opened Gmail compose via _launch_browser_url: subject='{clean_sub}' recipient='{recipient}'")
                return f"Opened Gmail with recipient '{recipient}', subject '{clean_sub}', and your message typed in ready to send."
            elif "linkedin" in app_name:
                import urllib.parse
                encoded_text = urllib.parse.quote(content)
                post_url = f"https://www.linkedin.com/feed/?shareActive=true&text={encoded_text}"
                _launch_browser_url(post_url)
                logger.info("Opened LinkedIn with draft post ready to publish.")
                return f"Opened LinkedIn with your post typed and ready to share."
            elif "twitter" in app_name or "x" in app_name or "tweet" in app_name:
                import urllib.parse
                encoded_text = urllib.parse.quote(content)
                tweet_url = f"https://twitter.com/intent/tweet?text={encoded_text}"
                _launch_browser_url(tweet_url)
                logger.info("Opened Twitter with draft tweet ready to post.")
                return f"Opened Twitter with your post typed and ready to tweet."
            else:
                # Default to Notepad for essays, notes, documents
                import subprocess
                import time
                import pyautogui
                import pyperclip
                pyautogui.FAILSAFE = False

                # Launch notepad
                subprocess.Popen("notepad.exe")
                time.sleep(1.0)

                # Type content live on screen word by word with smooth cadence
                words = content.split(" ")
                for word in words:
                    pyperclip.copy(word + " ")
                    pyautogui.hotkey("ctrl", "v")
                    time.sleep(0.04)

                return f"Opened Notepad and typed the complete text live on your screen."
        except Exception as e:
            logger.error(f"Error in type_in_application: {e}")
            return f"Error typing in application: {e}"

    res = await loop.run_in_executor(None, _type_sync)
    if auto_send and ("gmail" in app_name or "mail" in app_name or "email" in app_name):
        from voice_speech.engine.browser.dom_inspector import send_browser_draft
        await asyncio.sleep(5.0)
        send_res = await send_browser_draft("gmail")
        return f"{res} {send_res}"
    return res


async def _handle_inspect_browser_tab(args: Dict[str, Any]) -> str:
    from voice_speech.engine.browser.dom_inspector import inspect_browser_tab
    target = str((args or {}).get("target", "active")).strip()
    return await inspect_browser_tab(target)


async def _handle_send_current_draft(args: Dict[str, Any]) -> str:
    from voice_speech.engine.browser.dom_inspector import send_browser_draft
    target = str((args or {}).get("target", "gmail")).strip()
    return await send_browser_draft(target)


async def _handle_write_code_in_browser(args: Dict[str, Any]) -> str:
    from voice_speech.engine.browser.dom_inspector import type_code_in_browser
    code = str((args or {}).get("code", "")).strip()
    target = str((args or {}).get("target", "leetcode")).strip()
    auto_run = bool((args or {}).get("auto_run", True))
    auto_submit = bool((args or {}).get("auto_submit", False))
    return await type_code_in_browser(code=code, target=target, auto_run=auto_run, auto_submit=auto_submit)


async def _handle_next_leetcode_question(args: Dict[str, Any]) -> str:
    from voice_speech.engine.browser.dom_inspector import next_leetcode_question
    return await next_leetcode_question()


async def _handle_solve_leetcode_problem(args: Dict[str, Any]) -> str:
    from voice_speech.engine.browser.dom_inspector import solve_leetcode_problem
    pick_random = bool((args or {}).get("pick_random", False))
    auto_run = bool((args or {}).get("auto_run", True))
    auto_submit = bool((args or {}).get("auto_submit", False))
    return await solve_leetcode_problem(pick_random=pick_random, auto_run=auto_run, auto_submit=auto_submit)


# Extensible Tool Handler Registry
TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Awaitable[str]]] = {
    "get_latest_news": _handle_get_latest_news,
    "delegate_to_orchestrator": _handle_delegate_to_orchestrator,
    "open_application": _handle_open_application,
    "capture_photo": _handle_capture_photo,
    "type_in_application": _handle_type_in_application,
    "inspect_browser_tab": _handle_inspect_browser_tab,
    "send_current_draft": _handle_send_current_draft,
    "write_code_in_browser": _handle_write_code_in_browser,
    "next_leetcode_question": _handle_next_leetcode_question,
    "solve_leetcode_problem": _handle_solve_leetcode_problem,
}


async def dispatch_tool_call(name: str, args: Dict[str, Any]) -> str:
    """Dispatches a function call to the registered handler.

    Args:
        name: Name of the function declared in tool schema.
        args: Parsed argument dictionary from the model.

    Returns:
        String result to return to the model in FunctionResponse.
    """
    handler = TOOL_REGISTRY.get(name)
    if not handler:
        logger.warning(f"No handler registered for tool call '{name}'")
        return f"Tool '{name}' is not supported."

    logger.info(f"Executing tool call '{name}' with args={args}")
    try:
        return await handler(args)
    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
        return f"Error executing tool '{name}': {e}"
