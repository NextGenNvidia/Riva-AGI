"""Gemini Live Function Calling Tools & Registry.

Provides zero-key real-time news retrieval (Google News RSS + NewsAPI fallback)
and an extensible dispatcher registry for tool calls.
"""

import asyncio
import json
import logging
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Awaitable, Callable, Dict, List
from google.genai import types

logger = logging.getLogger("riva.tools")


async def fetch_news_summary(query: str) -> str:
    """Fetches a 3-headline news summary using NewsAPI (if key provided) or Google News RSS (zero key)."""
    clean_query = query.strip()
    if not clean_query:
        clean_query = "top world news"

    news_api_key = os.getenv("NEWS_API_KEY", "").strip()
    loop = asyncio.get_running_loop()

    # 1. Optional NewsAPI.org query (if key provided)
    if news_api_key:
        try:
            encoded = urllib.parse.quote(clean_query)
            url = f"https://newsapi.org/v2/everything?q={encoded}&pageSize=3&sortBy=publishedAt&apiKey={news_api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "RivaVoice/1.0"})

            def _fetch_newsapi():
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    return resp.read()

            raw_json = await loop.run_in_executor(None, _fetch_newsapi)
            data = json.loads(raw_json)
            articles = data.get("articles", [])
            headlines = [a.get("title", "").strip() for a in articles if a.get("title")]
            if headlines:
                summary = " | ".join(headlines[:3])[:320]
                logger.info(f"Live NewsAPI response for '{clean_query}': {summary!r}")
                return summary
        except Exception as e:
            logger.warning(f"NewsAPI error (falling back to Google News RSS): {e}")

    # 2. Universal Zero-Key Fallback: Google News RSS
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


# Tool Declarations
NEWS_TOOL_DECLARATION = types.FunctionDeclaration(
    name="get_latest_news",
    description=(
        "Fetch a brief summary of current/recent news or facts on a topic. "
        "Only call this when the user explicitly asks about recent events, current data, "
        "or information that requires up-to-date knowledge beyond your training."
    ),
    parameters=types.Schema(
        type="OBJECT",
        properties={"query": types.Schema(type="STRING", description="Search query")},
        required=["query"],
    ),
)

DEFAULT_TOOLS: List[types.Tool] = [
    types.Tool(function_declarations=[NEWS_TOOL_DECLARATION])
]


async def _handle_get_latest_news(args: Dict[str, Any]) -> str:
    query = str((args or {}).get("query", ""))
    return await fetch_news_summary(query)


# Extensible Tool Handler Registry
TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Awaitable[str]]] = {
    "get_latest_news": _handle_get_latest_news,
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
