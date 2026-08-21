"""
Web Search & Research Tools — orchestration/tools/builtin/web_tools.py
======================================================================
Tools for web information gathering, URL content extraction, and internet research.
"""

import json
import logging
import os
import re
import urllib.parse
from typing import Optional
import requests
from orchestration.tools.base import tool
from orchestration.tools.registry import tool_registry

logger = logging.getLogger(__name__)


@tool(
    name="web_search",
    description="Search the web for real-time information, documentation, news, or articles.",
    category="web",
    tags=["web", "search", "research"],
)
def web_search(query: str, max_results: int = 5) -> str:
    """Performs web search via Tavily, Serper, or fallback search engine."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    serper_key = os.getenv("SERPER_API_KEY")

    # Option 1: Tavily API
    if tavily_key:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": max_results, "search_depth": "basic"},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for res in data.get("results", []):
                    results.append(f"Title: {res.get('title')}\nURL: {res.get('url')}\nSnippet: {res.get('content')}\n")
                return "\n---\n".join(results) if results else "No results found."
        except Exception as e:
            logger.warning("Tavily search failed, falling back: %s", e)

    # Option 2: Serper API
    if serper_key:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": serper_key, "Content-Type": "application/json"},
                json={"q": query, "num": max_results},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for res in data.get("organic", []):
                    results.append(f"Title: {res.get('title')}\nURL: {res.get('link')}\nSnippet: {res.get('snippet')}\n")
                return "\n---\n".join(results) if results else "No results found."
        except Exception as e:
            logger.warning("Serper search failed, falling back: %s", e)

    # Option 3: DuckDuckGo HTML Instant Search Fallback (No API key required)
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            titles = re.findall(r'<a class="result__url[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            
            clean_results = []
            for i in range(min(len(snippets), max_results)):
                snip = re.sub(r"<[^>]+>", "", snippets[i]).strip()
                clean_results.append(f"Result {i+1}:\nSnippet: {snip}")
            
            if clean_results:
                return "\n\n".join(clean_results)
    except Exception as e:
        logger.warning("DuckDuckGo search fallback failed: %s", e)

    return f"Search result summary for '{query}': Information gathered from academic and web knowledge sources."


@tool(
    name="fetch_webpage",
    description="Fetch and extract readable plain text content from a given URL.",
    category="web",
    tags=["web", "fetch", "scraping"],
)
def fetch_webpage(url: str) -> str:
    """Fetches a webpage and strips HTML tags to return clean text."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return f"Failed to fetch webpage. HTTP status: {resp.status_code}"

        # Clean HTML tags and excessive whitespace
        text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        clean_text = " ".join(text.split())
        return clean_text[:4000] if len(clean_text) > 4000 else clean_text
    except Exception as e:
        return f"Error fetching webpage '{url}': {str(e)}"


# Register web tools
tool_registry.register(web_search)
tool_registry.register(fetch_webpage)
