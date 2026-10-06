"""
Browser Automation & DOM Tools — orchestration/tools/builtin/browser_tools.py
=============================================================================
High-performance, cognitive browser actuators for the Riva-AGI Orchestrator.
Connects directly to Microsoft Edge (CDP port 9222) to inspect semantic DOM,
extract problem specifications, stream code live into Monaco/web editors,
execute test suites with visual neon feedback, and retrieve test outcomes for self-healing.
"""
import asyncio
import concurrent.futures
import json
import logging
import os
import re
from typing import Any, Dict, Optional

from orchestration.tools.registry import tool
try:
    from voice_speech.engine.browser.dom_inspector import (
        DEFAULT_CDP_URL,
        bring_browser_window_to_foreground,
        try_launch_browser,
    )
except ImportError:
    DEFAULT_CDP_URL = "http://127.0.0.1:9222"
    def bring_browser_window_to_foreground(target_hint: str = "") -> bool:
        return False
    async def try_launch_browser():
        return False

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None


def _run_async(coro):
    """Safely executes an async coroutine synchronously in any thread environment."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)
    except Exception as e:
        logger.error(f"[BrowserTools] Async execution error: {e}")
        return json.dumps({"error": str(e)})


async def _get_cdp_browser(p, timeout_ms: int = 1500):
    """Connects to Microsoft Edge over CDP, auto-launching if needed."""
    browser = None
    for _ in range(3):
        try:
            browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL, timeout=timeout_ms)
            if browser:
                return browser
        except Exception:
            await asyncio.sleep(0.2)

    # Auto-launch Edge with CDP enabled if not already active
    default_url = os.environ.get("BROWSER_DEFAULT_URL", "https://leetcode.com/problemset/")
    launched = try_launch_browser("edge", default_url)
    if launched:
        await asyncio.sleep(1.5)
        try:
            browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL, timeout=2000)
            if browser:
                return browser
        except Exception:
            pass

    # Direct launch of visible Microsoft Edge on user desktop
    try:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        if browser:
            logger.info("[BrowserTools] Launched visible Microsoft Edge window on user desktop.")
            return browser
    except Exception as e:
        logger.warning(f"[BrowserTools] Edge desktop launch failed: {e}")

    return None


async def _async_inspect_browser_dom(target: str = "active") -> str:
    if async_playwright is None:
        return json.dumps({"error": "Playwright is not available in the Python environment."})

    async with async_playwright() as p:
        browser = await _get_cdp_browser(p)
        if not browser:
            return json.dumps({
                "error": "Could not connect to Microsoft Edge via CDP port 9222. Please ensure Edge is open."
            })

        target_page = None
        target_lower = target.lower().strip()

        # Find matching page
        problem_page = None
        general_page = None
        for context in browser.contexts:
            for page in context.pages:
                u = page.url.lower()
                if any(x in u for x in ["leetcode.com/problems/", "hackerrank.com/challenges/", "codeforces.com/problemset/"]) and "random-one-question" not in u:
                    problem_page = page
                    break
                elif target_lower in u or any(x in u for x in ["leetcode.com", "hackerrank.com", "codeforces.com", "geeksforgeeks.org"]):
                    general_page = page
            if problem_page:
                break

        target_page = problem_page or general_page
        if not target_page:
            for context in browser.contexts:
                if context.pages:
                    target_page = context.pages[0]
                    break

        if not target_page:
            return json.dumps({"error": "No open browser tab found."})

        await target_page.bring_to_front()
        bring_browser_window_to_foreground("edge")

        # Fast single-batch JS evaluate to extract all semantic attributes in <1.0s
        data = await target_page.evaluate("""() => {
            const titleEl = document.querySelector('.text-title-large') || 
                            document.querySelector('div[class*="title"]') || 
                            document.querySelector('h1');
            const descEl = document.querySelector('[data-track-load="description_content"]') || 
                           document.querySelector('.elfjS') || 
                           document.querySelector('article') || 
                           document.querySelector('main');
            
            const models = (window.monaco && window.monaco.editor) ? window.monaco.editor.getModels() : [];
            const model = models.length > 0 ? models[0] : null;
            const langBtn = document.querySelector('button[id*="headlessui-listbox-button"]') || 
                            document.querySelector('.ant-select-selection-item');

            let starterTemplate = '';
            let language = 'python';
            if (model) {
                starterTemplate = model.getValue();
                language = model.getLanguageId() || 'python';
            } else {
                const ta = document.querySelector('textarea, div[contenteditable="true"]');
                if (ta) starterTemplate = ta.value || ta.innerText || '';
            }

            if (langBtn && langBtn.innerText) {
                language = langBtn.innerText.trim().toLowerCase();
            }

            return {
                title: titleEl ? titleEl.innerText.trim() : document.title,
                url: window.location.href,
                description: descEl ? descEl.innerText.slice(0, 2000).trim() : '',
                template: starterTemplate,
                language: language
            };
        }""")

        return json.dumps(data, indent=2)


@tool(category="browser")
def inspect_browser_dom(target: str = "active") -> str:
    """
    Inspects the currently active browser tab in Microsoft Edge over CDP.
    Extracts the page title, problem statement, description, constraints,
    programming language, and starter code template from the Monaco editor.
    Returns structured JSON.
    """
    return _run_async(_async_inspect_browser_dom(target))


async def _async_stream_code_to_editor(code: str, target: str = "active", speed_ms: int = 12) -> str:
    if async_playwright is None:
        return json.dumps({"error": "Playwright is not available."})

    clean_code = code.strip()
    if not clean_code:
        return json.dumps({"error": "No code provided to stream."})

    bring_browser_window_to_foreground("edge")

    async with async_playwright() as p:
        browser = await _get_cdp_browser(p)
        if not browser:
            return json.dumps({"error": "Could not connect to browser via CDP."})

        target_page = None
        for context in browser.contexts:
            for page in context.pages:
                u = page.url.lower()
                if any(x in u for x in ["leetcode.com/problems/", "hackerrank.com", "codeforces.com", "geeksforgeeks.org"]):
                    target_page = page
                    break
                elif target.lower() in u or "leetcode.com" in u:
                    target_page = page
            if target_page:
                break

        if not target_page:
            for context in browser.contexts:
                if context.pages:
                    target_page = context.pages[0]
                    break

        if not target_page:
            return json.dumps({"error": "No open editor tab found."})

        await target_page.bring_to_front()
        bring_browser_window_to_foreground("edge")
        await asyncio.sleep(0.15)

        # Ultra-fast typewriter animation (10-12ms cadence) with Monaco cursor tracking
        res = await target_page.evaluate("""async ({ code, speed }) => {
            const models = (window.monaco && window.monaco.editor) ? window.monaco.editor.getModels() : [];
            if (!models.length) {
                const ta = document.querySelector('textarea, div[contenteditable="true"]');
                if (ta) {
                    ta.focus();
                    ta.value = code;
                    return { success: true, method: 'textarea' };
                }
                return { success: false, reason: 'No editor found on page' };
            }
            const model = models[0];
            const editors = window.monaco.editor.getEditors ? window.monaco.editor.getEditors() : [];
            const editor = editors.length > 0 ? editors[0] : null;

            if (editor) editor.focus();
            model.setValue('');

            const lines = code.split('\\n');
            let accumulated = '';
            for (let i = 0; i < lines.length; i++) {
                accumulated += (i > 0 ? '\\n' : '') + lines[i];
                model.setValue(accumulated);
                if (editor) {
                    const curLine = model.getLineCount();
                    editor.setPosition({ lineNumber: curLine, column: model.getLineMaxColumn(curLine) });
                    editor.revealLine(curLine);
                }
                if (speed > 0) {
                    await new Promise(r => setTimeout(r, speed));
                }
            }
            return { success: true, lines_typed: lines.length, method: 'monaco' };
        }""", {"code": clean_code, "speed": speed_ms})

        return json.dumps(res, indent=2)


@tool(category="browser")
def stream_code_to_editor(code: str, target: str = "active", speed_ms: int = 12) -> str:
    """
    Streams code live into the browser code editor (Monaco or textarea) with line-by-line
    typing animation and cursor tracking. Does not lock or hijack the physical mouse.
    Returns execution status JSON.
    """
    return _run_async(_async_stream_code_to_editor(code, target, speed_ms))


async def _async_run_browser_code() -> str:
    if async_playwright is None:
        return json.dumps({"error": "Playwright is not available."})

    async with async_playwright() as p:
        browser = await _get_cdp_browser(p)
        if not browser:
            return json.dumps({"error": "Could not connect to browser via CDP."})

        target_page = None
        for context in browser.contexts:
            for page in context.pages:
                u = page.url.lower()
                if any(x in u for x in ["leetcode.com", "hackerrank.com", "codeforces.com", "geeksforgeeks.org"]):
                    target_page = page
                    break
            if target_page:
                break

        if not target_page:
            for context in browser.contexts:
                if context.pages:
                    target_page = context.pages[0]
                    break

        if not target_page:
            return json.dumps({"error": "No active browser tab found."})

        # Visually highlight and click the Run button
        click_res = await target_page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const runBtn = btns.find(b => {
                const txt = (b.innerText || '').trim().toLowerCase();
                const testId = b.getAttribute('data-e2e-locator') || '';
                return txt === 'run' || txt.startsWith('run ') || testId === 'console-run-button';
            });
            if (runBtn) {
                runBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                runBtn.style.transition = 'all 0.2s ease';
                runBtn.style.transform = 'scale(1.15)';
                runBtn.style.boxShadow = '0 0 25px #00ff88, 0 0 45px #00ff88';
                runBtn.style.border = '2px solid #00ff88';
                runBtn.click();
                return { clicked: true, method: 'dom_button' };
            }
            return { clicked: false, method: 'hotkey_needed' };
        }""")

        if not click_res.get("clicked"):
            await target_page.keyboard.press("Control+Enter")

        # Fast polling for test results (up to 4.0s, polling every 250ms)
        status = "Pending"
        details = ""
        for _ in range(16):
            await asyncio.sleep(0.25)
            poll_res = await target_page.evaluate("""() => {
                const bodyText = document.body.innerText;
                const acceptedEl = Array.from(document.querySelectorAll('div, span')).find(el => {
                    const t = (el.innerText || '').trim();
                    return t === 'Accepted' && el.children.length === 0;
                });
                if (acceptedEl) {
                    return { status: 'Accepted', details: 'All test cases passed successfully.' };
                }
                if (bodyText.includes('Wrong Answer')) {
                    return { status: 'Wrong Answer', details: 'One or more test cases produced unexpected output.' };
                }
                if (bodyText.includes('Runtime Error')) {
                    return { status: 'Runtime Error', details: 'An unhandled exception occurred during execution.' };
                }
                if (bodyText.includes('Compile Error')) {
                    return { status: 'Compile Error', details: 'Syntax or type compilation error in code.' };
                }
                if (bodyText.includes('Time Limit Exceeded')) {
                    return { status: 'Time Limit Exceeded', details: 'Algorithm exceeded time limits. Need O(N) optimization.' };
                }
                return null;
            }""")
            if poll_res and poll_res.get("status"):
                status = poll_res["status"]
                details = poll_res.get("details", "")
                break

        return json.dumps({"status": status, "details": details}, indent=2)


@tool(category="browser")
def run_browser_code() -> str:
    """
    Visually highlights and clicks the Run button in the browser code editor,
    executes the test cases, and polls the console for results (Accepted, Wrong Answer, etc.).
    Returns outcome JSON.
    """
    return _run_async(_async_run_browser_code())


async def _async_submit_browser_code() -> str:
    if async_playwright is None:
        return json.dumps({"error": "Playwright is not available."})

    async with async_playwright() as p:
        browser = await _get_cdp_browser(p)
        if not browser:
            return json.dumps({"error": "Could not connect to browser via CDP."})

        target_page = None
        for context in browser.contexts:
            for page in context.pages:
                u = page.url.lower()
                if any(x in u for x in ["leetcode.com", "hackerrank.com", "codeforces.com", "geeksforgeeks.org"]):
                    target_page = page
                    break
            if target_page:
                break

        if not target_page:
            for context in browser.contexts:
                if context.pages:
                    target_page = context.pages[0]
                    break

        if not target_page:
            return json.dumps({"error": "No active browser tab found."})

        # Visually highlight and click Submit button
        await target_page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const submitBtn = btns.find(b => {
                const txt = (b.innerText || '').trim().toLowerCase();
                const testId = b.getAttribute('data-e2e-locator') || '';
                return txt === 'submit' || testId === 'console-submit-button';
            });
            if (submitBtn) {
                submitBtn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                submitBtn.style.transition = 'all 0.2s ease';
                submitBtn.style.transform = 'scale(1.15)';
                submitBtn.style.boxShadow = '0 0 25px #3b82f6, 0 0 45px #3b82f6';
                submitBtn.style.border = '2px solid #3b82f6';
                submitBtn.click();
            }
        }""")

        await asyncio.sleep(2.0)
        return json.dumps({"status": "Submitted", "details": "Code submitted to online judge."}, indent=2)


@tool(category="browser")
def submit_browser_code() -> str:
    """
    Visually highlights and clicks the Submit button in the browser editor to submit the solution.
    Returns outcome JSON.
    """
    return _run_async(_async_submit_browser_code())


async def _async_navigate_browser(url: str) -> str:
    if async_playwright is None:
        return json.dumps({"error": "Playwright is not available."})

    async with async_playwright() as p:
        browser = await _get_cdp_browser(p)
        if not browser:
            return json.dumps({"error": "Could not connect to browser via CDP."})

        target_page = None
        for context in browser.contexts:
            if context.pages:
                target_page = context.pages[0]
                break

        if not target_page:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            target_page = await context.new_page()

        await target_page.goto(url, wait_until="domcontentloaded", timeout=12000)
        bring_browser_window_to_foreground()
        title = await target_page.title()
        return json.dumps({"status": "Navigated", "title": title, "url": target_page.url}, indent=2)


@tool(category="browser")
def navigate_browser(url: str) -> str:
    """
    Navigates the open browser tab to a specified URL and brings the window to the foreground.
    Returns status JSON.
    """
    return _run_async(_async_navigate_browser(url))
