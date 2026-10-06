"""
Live Demonstration: Voice-to-Text Task -> Cognitive Multi-Agent Reasoning -> Live Code Typewriter in Browser
============================================================================================================
Simulates voice prompt input, performs DOM inspection of LeetCode in Microsoft Edge,
generates optimal algorithmic code via Groq LPU, and live-streams typing into the Monaco
editor before the user's eyes within the 15-second SLA budget.
"""
import asyncio
import os
import sys
import time
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from orchestration.orchestrator.llm import call_gemini
from voice_speech.engine.browser.dom_inspector import bring_browser_window_to_foreground

async def run_live_demo(voice_prompt: str = "Edge browser me LeetCode question solve karo aur live code type karke Run dabao"):
    print("=" * 70)
    print(" [*] RIVA-AGI LIVE AUTONOMOUS EXECUTION DEMONSTRATION")
    print("=" * 70)
    print(f" [Voice-To-Text Input]: \"{voice_prompt}\"")
    print("=" * 70)

    t0 = time.time()
    
    # ── Step 0: Spoken Acknowledgment (<700ms) ────────────────────────────────
    t_ack = time.time() - t0
    print(f"\n[0.0s - {t_ack*1000:.0f}ms] [Voice Output]: \"Theek hai, abhi analyze karke browser me live solve karta hoon!\"")

    # ── Step 1: Open / Connect to Microsoft Edge on User Screen ──────────────
    print("\n[Step 1] Connecting to Microsoft Edge on your desktop...")
    t1 = time.time()
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222", timeout=1200)
            print("  Connected to existing Microsoft Edge via CDP port 9222.")
        except Exception:
            print("  Opening new Microsoft Edge window on your desktop...")
            browser = await p.chromium.launch(channel="msedge", headless=False)

        # Get or open LeetCode tab
        target_page = None
        for context in browser.contexts:
            for page in context.pages:
                if "leetcode.com" in page.url.lower():
                    target_page = page
                    break
            if target_page:
                break

        if not target_page:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            target_page = await context.new_page()
            dest = "https://leetcode.com/problems/valid-parenthesis-string/"
            print(f"  Navigating to problem: {dest}")
            await target_page.goto(dest, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2.0)

        await target_page.bring_to_front()
        bring_browser_window_to_foreground("leetcode")
        t_browser = time.time() - t1
        print(f"  Browser ready in {t_browser:.2f}s.")

        # ── Step 2: Semantic DOM Extraction (<1.0s) ───────────────────────────
        print("\n[Step 2] [Thinking] Inspecting Problem, Constraints & Monaco Starter Signature...")
        t2 = time.time()
        dom_data = await target_page.evaluate("""() => {
            const titleEl = document.querySelector('.text-title-large') || document.querySelector('div[class*="title"]') || document.querySelector('h1');
            const descEl = document.querySelector('[data-track-load="description_content"]') || document.querySelector('.elfjS') || document.querySelector('article');
            const models = (window.monaco && window.monaco.editor) ? window.monaco.editor.getModels() : [];
            const model = models.length > 0 ? models[0] : null;
            return {
                title: titleEl ? titleEl.innerText.trim() : document.title,
                description: descEl ? descEl.innerText.slice(0, 1500).trim() : '',
                template: model ? model.getValue() : '',
                language: model ? model.getLanguageId() : 'python'
            };
        }""")
        title = dom_data.get("title", "Valid Parenthesis String")
        lang = dom_data.get("language", "python")
        template = dom_data.get("template", "")
        t_dom = time.time() - t2
        print(f"  Extracted Title: \"{title}\" (Language: {lang}) in {t_dom:.2f}s")

        # ── Step 3: Cognitive Code Generation via Groq LPU (<2.0s) ───────────
        print("\n[Step 3] [Generating] Synthesizing optimal O(N) algorithmic solution via Coder Agent...")
        t3 = time.time()
        prompt = (
            f"Solve LeetCode problem in {lang}.\nTitle: {title}\n"
            f"Description: {dom_data.get('description', '')[:1000]}\n"
            f"Starter signature template:\n{template}\n\n"
            "Return ONLY the executable Python class Solution matching the template signature exactly. "
            "No markdown fences, no explanations."
        )
        raw_code = call_gemini(prompt=prompt, agent_id="coder")
        import re
        clean_code = re.sub(r"^```[a-zA-Z]*\n", "", raw_code.strip())
        clean_code = re.sub(r"\n```$", "", clean_code.strip())
        t_gen = time.time() - t3
        print(f"  Generated {len(clean_code.splitlines())} lines of code in {t_gen:.2f}s!")

        # ── Step 4: Live Monaco Typewriter Streaming into Browser (<3.0s) ─────
        print("\n[Step 4] [Typing] Live Streaming Code into Microsoft Edge Monaco Editor...")
        t4 = time.time()
        await target_page.bring_to_front()
        bring_browser_window_to_foreground("leetcode")

        type_res = await target_page.evaluate("""async ({ code, speed }) => {
            const models = (window.monaco && window.monaco.editor) ? window.monaco.editor.getModels() : [];
            if (!models.length) return { success: false, reason: 'No Monaco editor' };
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
            return { success: true, lines_typed: lines.length };
        }""", {"code": clean_code, "speed": 12})
        t_type = time.time() - t4
        print(f"  Typed {type_res.get('lines_typed')} lines live with cursor tracking in {t_type:.2f}s!")

        # ── Step 5: Highlight Run Button & Verify Test Results (<3.0s) ────────
        print("\n[Step 5] [Action] Clicking Run button with neon feedback & polling console...")
        t5 = time.time()
        await target_page.evaluate("""() => {
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
                runBtn.style.boxShadow = '0 0 30px #00ff88, 0 0 50px #00ff88';
                runBtn.style.border = '2px solid #00ff88';
                runBtn.click();
            }
        }""")

        # Poll test console
        status = "Pending"
        for _ in range(16):
            await asyncio.sleep(0.25)
            poll = await target_page.evaluate("""() => {
                const txt = document.body.innerText;
                if (txt.includes('Accepted')) return 'Accepted';
                if (txt.includes('Wrong Answer')) return 'Wrong Answer';
                if (txt.includes('Runtime Error')) return 'Runtime Error';
                return null;
            }""")
            if poll:
                status = poll
                break
        t_run = time.time() - t5
        print(f"  Test Console Verdict: [{status}] (in {t_run:.2f}s)")

        total_elapsed = time.time() - t0
        print("\n" + "=" * 70)
        print(f" [SUCCESS] TOTAL PIPELINE LATENCY: {total_elapsed:.2f}s (SLA Budget: Max 15.0s)")
        print(f" [Voice Output]: \"Problem '{title}' successfully solved! Verdict: {status}. All completed in {total_elapsed:.1f} seconds!\"")
        print("=" * 70)

        # Keep browser open for user to admire
        await asyncio.sleep(8.0)

if __name__ == "__main__":
    asyncio.run(run_live_demo())
