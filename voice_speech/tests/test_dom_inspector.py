import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from voice_speech.engine.browser.dom_inspector import (
    is_domain_blocked,
    DOMInspector,
    inspect_browser_tab
)
from voice_speech.engine.gemini.tools import (
    INSPECT_BROWSER_TAB_DECLARATION,
    DEFAULT_TOOLS,
    TOOL_REGISTRY,
    dispatch_tool_call
)


def test_privacy_sandbox_domain_blocking():
    # Blocked domains (Private messaging, banking, auth)
    assert is_domain_blocked("web.whatsapp.com") is True
    assert is_domain_blocked("https://web.whatsapp.com/chat/123") is True
    assert is_domain_blocked("whatsapp") is True
    assert is_domain_blocked("web.telegram.org") is True
    assert is_domain_blocked("https://chase.bank.com") is True
    assert is_domain_blocked("netbanking") is True
    assert is_domain_blocked("instagram.com") is True

    # Allowed productive domains
    assert is_domain_blocked("https://leetcode.com/problems/two-sum") is False
    assert is_domain_blocked("leetcode") is False
    assert is_domain_blocked("https://mail.google.com/mail/u/0/") is False
    assert is_domain_blocked("gmail") is False
    assert is_domain_blocked("https://github.com/NextGenNvidia") is False


@pytest.mark.asyncio
async def test_inspect_blocked_domain_halts_immediately():
    inspector = DOMInspector()
    result = await inspector.inspect(target="whatsapp")
    assert "Privacy Gate" in result
    assert "restricted" in result.lower()
    assert "whatsapp" in result.lower()


@pytest.mark.asyncio
async def test_extract_leetcode_context_mock():
    inspector = DOMInspector()
    mock_page = AsyncMock()
    mock_page.title.return_value = "Two Sum - LeetCode"
    mock_page.evaluate.side_effect = [
        # 1. problem_info
        {"title": "1. Two Sum", "description": "Given an array of integers nums and an integer target..."},
        # 2. editor_data
        {
            "code": "def twoSum(nums, target):\n    prevMap = {}\n    for i, n in enumerate(nums):\n        diff = target - n\n        if diff in prevMap:\n            return [prevMap[diff], i]\n        prevMap[n] = i",
            "language": "Python3",
            "testResult": "Accepted (All 3 testcases passed)"
        }
    ]

    result = await inspector.extract_leetcode_context(mock_page)
    assert "LeetCode Active Context" in result
    assert "1. Two Sum" in result
    assert "Python3" in result
    assert "def twoSum(nums, target):" in result
    assert "Accepted" in result


@pytest.mark.asyncio
async def test_extract_gmail_context_mock():
    inspector = DOMInspector()
    mock_page = AsyncMock()
    mock_page.title.return_value = "Inbox (7) - user@gmail.com - Gmail"
    mock_page.evaluate.return_value = {
        "unreadCount": "7",
        "emails": [
            {"sender": "Google Security", "subject": "New login alert from Windows", "time": "10:30 AM"},
            {"sender": "GitHub", "subject": "PR #37 merged into main", "time": "9:15 AM"}
        ]
    }

    result = await inspector.extract_gmail_context(mock_page)
    assert "Gmail Inbox Status" in result
    assert "**Total Unread Emails**: **7**" in result
    assert "Google Security" in result
    assert "New login alert from Windows" in result
    assert "GitHub" in result


def test_inspect_browser_tab_tool_registration():
    # Verify declaration exists in DEFAULT_TOOLS
    tool_names = [fn.name for t in DEFAULT_TOOLS for fn in t.function_declarations]
    assert "inspect_browser_tab" in tool_names

    # Verify registered in handler dispatch map
    assert "inspect_browser_tab" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_extract_generic_context_mock():
    inspector = DOMInspector()
    mock_page = AsyncMock()
    mock_page.title.return_value = "Python Requests Documentation - Quickstart"
    mock_page.url = "https://requests.readthedocs.io/en/latest/user/quickstart/"
    mock_page.evaluate.return_value = {
        "headings": ["Quickstart", "Make a Request", "Response Content"],
        "bodySnippet": "Making a request with Requests is very simple. Begin by importing the Requests module...",
        "codeBlocks": ["r = requests.get('https://api.github.com/user', auth=('user', 'pass'))"],
        "buttons": ["Search", "Next"]
    }

    result = await inspector.extract_generic_context(mock_page)
    assert "Web Tab Context: Python Requests Documentation" in result
    assert "Quickstart" in result
    assert "Make a Request" in result
    assert "r = requests.get" in result
    assert "Search" in result


@pytest.mark.asyncio
async def test_dispatch_tool_call_inspect_browser_tab():
    with patch("voice_speech.engine.browser.dom_inspector.DOMInspector.inspect") as mock_inspect:
        mock_inspect.return_value = "### LeetCode Context: Two Sum"

        result = await dispatch_tool_call("inspect_browser_tab", {"target": "leetcode"})
        assert result == "### LeetCode Context: Two Sum"
        mock_inspect.assert_called_once_with("leetcode")


def test_send_current_draft_tool_registration():
    tool_names = [fn.name for t in DEFAULT_TOOLS for fn in t.function_declarations]
    assert "send_current_draft" in tool_names
    assert "send_current_draft" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_dispatch_tool_call_send_current_draft():
    with patch("voice_speech.engine.browser.dom_inspector.send_browser_draft", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "✅ Email sent successfully!"

        result = await dispatch_tool_call("send_current_draft", {"target": "gmail"})
        assert "Email sent successfully" in result
        mock_send.assert_called_once_with("gmail")


def test_write_code_in_browser_tool_registration():
    tool_names = [fn.name for t in DEFAULT_TOOLS for fn in t.function_declarations]
    assert "write_code_in_browser" in tool_names
    assert "write_code_in_browser" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_dispatch_tool_call_write_code_in_browser():
    with patch("voice_speech.engine.browser.dom_inspector.type_code_in_browser", new_callable=AsyncMock) as mock_type:
        mock_type.return_value = "✅ Code live-streamed and typed directly into Monaco editor on your screen! Run Verdict: Accepted"

        result = await dispatch_tool_call("write_code_in_browser", {"code": "class Solution {}", "auto_run": True})
        assert "Code live-streamed" in result
        assert "Accepted" in result
        mock_type.assert_called_once_with(code="class Solution {}", target="leetcode", auto_run=True, auto_submit=False)


def test_next_leetcode_question_tool_registration():
    tool_names = [fn.name for t in DEFAULT_TOOLS for fn in t.function_declarations]
    assert "next_leetcode_question" in tool_names
    assert "next_leetcode_question" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_dispatch_tool_call_next_leetcode_question():
    with patch("voice_speech.engine.browser.dom_inspector.next_leetcode_question", new_callable=AsyncMock) as mock_next:
        mock_next.return_value = "✅ Naya random LeetCode question open ho chuka hai: 'Two Sum'."

        result = await dispatch_tool_call("next_leetcode_question", {})
        assert "Naya random LeetCode question" in result
        assert "Two Sum" in result
        mock_next.assert_called_once()


def test_solve_leetcode_problem_tool_registration():
    tool_names = [fn.name for t in DEFAULT_TOOLS for fn in t.function_declarations]
    assert "solve_leetcode_problem" in tool_names
    assert "solve_leetcode_problem" in TOOL_REGISTRY


@pytest.mark.asyncio
async def test_dispatch_tool_call_solve_leetcode_problem():
    with patch("voice_speech.engine.browser.dom_inspector.solve_leetcode_problem", new_callable=AsyncMock) as mock_solve:
        mock_solve.return_value = "✅ Solved 'Two Sum' on LeetCode! Run Test Result: Accepted"

        result = await dispatch_tool_call("solve_leetcode_problem", {"pick_random": True})
        assert "Solved 'Two Sum'" in result
        assert "Accepted" in result
        mock_solve.assert_called_once_with(pick_random=True, auto_run=True, auto_submit=False)


def test_extract_leetcode_problem_title():
    from voice_speech.engine.browser.dom_inspector import extract_leetcode_problem_title, is_leetcode_problem_title

    assert extract_leetcode_problem_title("2884. Modify Columns - LeetCode - Personal - Microsoft Edge") == "2884. Modify Columns"
    assert extract_leetcode_problem_title("Two Sum - LeetCode - Microsoft Edge") == "Two Sum"
    assert extract_leetcode_problem_title("1. Two Sum - LeetCode") == "1. Two Sum"
    assert extract_leetcode_problem_title("Problems - LeetCode - Personal - Microsoft Edge") == "Two Sum"
    assert extract_leetcode_problem_title("LeetCode at Your Fingertips - LeetCode", fallback="Two Sum") == "Two Sum"
    assert extract_leetcode_problem_title("LeetCode at Your Fingertips - LeetCode", fallback=None) is None

    # Test problem title discrimination
    assert is_leetcode_problem_title("2884. Modify Columns - LeetCode - Personal - Microsoft Edge") is True
    assert is_leetcode_problem_title("Two Sum - LeetCode - Microsoft Edge") is True
    assert is_leetcode_problem_title("1. Two Sum - LeetCode") is True
    assert is_leetcode_problem_title("Problems - LeetCode - Personal - Microsoft Edge") is False
    assert is_leetcode_problem_title("LeetCode at Your Fingertips - LeetCode") is False
    assert is_leetcode_problem_title("Discuss - LeetCode") is False
    assert is_leetcode_problem_title("") is False


def test_ensure_edge_cdp_running_does_not_spawn_processes():
    from voice_speech.engine.browser.dom_inspector import ensure_edge_cdp_running
    with patch("voice_speech.engine.browser.dom_inspector.is_cdp_active", return_value=False):
        assert ensure_edge_cdp_running() is False


@pytest.mark.asyncio
async def test_solve_leetcode_problem_falls_back_to_native_when_cdp_inactive():
    from voice_speech.engine.browser.dom_inspector import solve_leetcode_problem

    with patch("voice_speech.engine.browser.dom_inspector.async_playwright") as mock_pw, \
         patch("voice_speech.engine.browser.dom_inspector.solve_leetcode_natively", new_callable=AsyncMock) as mock_native:

        mock_p_instance = MagicMock()
        mock_p_instance.chromium.connect_over_cdp = AsyncMock(side_effect=Exception("CDP Port 9222 refused"))
        mock_pw.return_value.__aenter__.return_value = mock_p_instance

        mock_native.return_value = "✅ '2884. Modify Columns' solve ho gaya!"

        res = await solve_leetcode_problem()
        assert "solve ho gaya" in res
        mock_native.assert_called_once()
