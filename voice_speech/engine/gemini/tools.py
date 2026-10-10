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


# Ensure workspace root is available for imports
import sys
from pathlib import Path
_WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

from orchestration.tools import tool_registry
from orchestration.orchestrator.main import run_orchestrator

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
    name="ask_orchestrator",
    description=(
        "Delegate complex, multi-step, software development, coding, deep research, or multi-agent tasks to the Riva-AGI Orchestrator. "
        "Use this whenever the user wants to build a project, write multi-file code, perform deep reasoning, or run complex workflows."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "task": types.Schema(type="STRING", description="Detailed description of the task or prompt for the multi-agent orchestrator"),
        },
        required=["task"],
    ),
)

EXECUTE_COMMAND_DECLARATION = types.FunctionDeclaration(
    name="execute_command",
    description="Executes a system terminal or shell command safely on the host computer (Windows/Linux/Mac).",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "command": types.Schema(type="STRING", description="The command line string to execute in shell"),
        },
        required=["command"],
    ),
)

READ_FILE_DECLARATION = types.FunctionDeclaration(
    name="read_file",
    description="Reads the text content of a file from the filesystem.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "file_path": types.Schema(type="STRING", description="Path to the file to read"),
        },
        required=["file_path"],
    ),
)

WRITE_FILE_DECLARATION = types.FunctionDeclaration(
    name="write_file",
    description="Creates a new file or overwrites an existing file with the provided content.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "file_path": types.Schema(type="STRING", description="Destination path for the file"),
            "content": types.Schema(type="STRING", description="Text content to write to the file"),
        },
        required=["file_path", "content"],
    ),
)

EDIT_FILE_DECLARATION = types.FunctionDeclaration(
    name="edit_file",
    description="Edits an existing file by replacing target text with replacement text.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "file_path": types.Schema(type="STRING", description="Path to the file to edit"),
            "target_text": types.Schema(type="STRING", description="Exact text block to replace"),
            "replacement_text": types.Schema(type="STRING", description="New replacement text block"),
        },
        required=["file_path", "target_text", "replacement_text"],
    ),
)

LIST_DIRECTORY_DECLARATION = types.FunctionDeclaration(
    name="list_directory",
    description="Lists files and subdirectories in a directory path.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "dir_path": types.Schema(type="STRING", description="Directory path to inspect (default '.')"),
        },
    ),
)

GET_SYSTEM_INFO_DECLARATION = types.FunctionDeclaration(
    name="get_system_info",
    description="Retrieves information about host operating system, release version, Python runtime, and working directory.",
    parameters=types.Schema(
        type="OBJECT",
        properties={},
    ),
)

WEB_SEARCH_DECLARATION = types.FunctionDeclaration(
    name="web_search",
    description="Performs an instant web search to find current information and URLs on any topic.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "query": types.Schema(type="STRING", description="Search query keywords"),
        },
        required=["query"],
    ),
)

FETCH_URL_CONTENT_DECLARATION = types.FunctionDeclaration(
    name="fetch_url_content",
    description="Fetches and extracts clean readable text from a web page URL.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "url": types.Schema(type="STRING", description="URL to fetch content from"),
        },
        required=["url"],
    ),
)

DEFAULT_TOOLS: List[types.Tool] = [
    types.Tool(
        function_declarations=[
            NEWS_TOOL_DECLARATION,
            ORCHESTRATOR_TOOL_DECLARATION,
            EXECUTE_COMMAND_DECLARATION,
            READ_FILE_DECLARATION,
            WRITE_FILE_DECLARATION,
            EDIT_FILE_DECLARATION,
            LIST_DIRECTORY_DECLARATION,
            GET_SYSTEM_INFO_DECLARATION,
            WEB_SEARCH_DECLARATION,
            FETCH_URL_CONTENT_DECLARATION,
        ]
    )
]


async def _handle_get_latest_news(args: Dict[str, Any]) -> str:
    query = str((args or {}).get("query", ""))
    return await fetch_news_summary(query)


async def _handle_ask_orchestrator(args: Dict[str, Any]) -> str:
    task = str((args or {}).get("task", ""))
    loop = asyncio.get_running_loop()
    def _run():
        res = run_orchestrator(task)
        if res.get("response_payload") and hasattr(res["response_payload"], "content"):
            return res["response_payload"].content
        return "Orchestrator completed task."
    return await loop.run_in_executor(None, _run)


def _make_tool_executor(tool_name: str):
    async def _executor(args: Dict[str, Any]) -> str:
        loop = asyncio.get_running_loop()
        def _call():
            return tool_registry.execute(tool_name, **(args or {}))
        return await loop.run_in_executor(None, _call)
    return _executor


# Extensible Tool Handler Registry
TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Awaitable[str]]] = {
    "get_latest_news": _handle_get_latest_news,
    "ask_orchestrator": _handle_ask_orchestrator,
    "execute_command": _make_tool_executor("execute_command"),
    "read_file": _make_tool_executor("read_file"),
    "write_file": _make_tool_executor("write_file"),
    "edit_file": _make_tool_executor("edit_file"),
    "list_directory": _make_tool_executor("list_directory"),
    "get_system_info": _make_tool_executor("get_system_info"),
    "web_search": _make_tool_executor("web_search"),
    "fetch_url_content": _make_tool_executor("fetch_url_content"),
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

    logger.info(f"Executing voice tool call '{name}' with args={args}")
    try:
        return await handler(args)
    except Exception as e:
        logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
        return f"Error executing tool '{name}': {e}"
