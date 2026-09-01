import html
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from orchestration.tools.registry import tool

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)


def _clean_html_text(raw_html: str) -> str:
    """Strips script, style, HTML tags and normalizes whitespace from HTML string."""
    if not raw_html:
        return ""
    # Remove script and style elements
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", raw_html, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.IGNORECASE)
    # Remove HTML comments
    cleaned = re.sub(r"<!--[\s\S]*?-->", "", cleaned)
    # Remove remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Unescape HTML entities
    cleaned = html.unescape(cleaned)
    # Normalize whitespaces
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned)
    return cleaned.strip()


def _extract_ddg_url(raw_url: str) -> str:
    """Extracts actual destination URL from DuckDuckGo redirect link if present."""
    if not raw_url:
        return ""
    if raw_url.startswith("//"):
        raw_url = "https:" + raw_url
    if "duckduckgo.com/l/?" in raw_url or "/l/?uddg=" in raw_url:
        parsed = urllib.parse.urlparse(raw_url)
        params = urllib.parse.parse_qs(parsed.query)
        if "uddg" in params and params["uddg"]:
            return urllib.parse.unquote(params["uddg"][0])
    return raw_url


@tool(category="web")
def web_search(query: str, max_results: int = 5) -> str:
    """Performs a web search using DuckDuckGo and returns formatted markdown results.

    Args:
        query: Search keywords or query string.
        max_results: Maximum number of search results to return (default: 5).

    Returns:
        Formatted markdown containing numbered search results with Title, URL, and Snippet.
    """
    if not query or not query.strip():
        return "Error: Search query cannot be empty."

    try:
        encoded_query = urllib.parse.urlencode({"q": query})
        search_url = f"https://html.duckduckgo.com/html/?{encoded_query}"
        headers = {
            "User-Agent": _DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html_content = response.read().decode("utf-8", errors="replace")

        # Parse DuckDuckGo HTML results
        results: List[Dict[str, str]] = []

        # Find result containers
        result_blocks = re.findall(
            r'<div[^>]*class="[^"]*(?:result|result__body|links_main)[^"]*"[^>]*>([\s\S]*?)</div>\s*(?:</div>|</td>)',
            html_content,
            flags=re.IGNORECASE,
        )

        for block in result_blocks:
            # Extract link and title
            title_match = re.search(
                r'<a[^>]*class="[^"]*(?:result__a|result-link)[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',
                block,
                flags=re.IGNORECASE,
            )
            # Extract snippet
            snippet_match = re.search(
                r'<(?:a|td|div)[^>]*class="[^"]*(?:result__snippet|result-snippet)[^"]*"[^>]*>([\s\S]*?)</(?:a|td|div)>',
                block,
                flags=re.IGNORECASE,
            )

            if title_match:
                raw_url = title_match.group(1)
                raw_title = title_match.group(2)
                url = _extract_ddg_url(raw_url)
                title = _clean_html_text(raw_title)
                snippet = _clean_html_text(snippet_match.group(1)) if snippet_match else "No description available."

                if url and title:
                    results.append({"title": title, "url": url, "snippet": snippet})
                    if len(results) >= max_results:
                        break

        # Fallback regex if block parsing found nothing
        if not results:
            title_matches = list(re.finditer(
                r'<a[^>]*class="[^"]*(?:result__a|result-link)[^"]*"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',
                html_content,
                flags=re.IGNORECASE,
            ))
            snippet_matches = list(re.finditer(
                r'<(?:a|td|div)[^>]*class="[^"]*(?:result__snippet|result-snippet)[^"]*"[^>]*>([\s\S]*?)</(?:a|td|div)>',
                html_content,
                flags=re.IGNORECASE,
            ))

            for i, tm in enumerate(title_matches[:max_results]):
                raw_url = tm.group(1)
                raw_title = tm.group(2)
                url = _extract_ddg_url(raw_url)
                title = _clean_html_text(raw_title)
                snippet = "No description available."
                if i < len(snippet_matches):
                    snippet = _clean_html_text(snippet_matches[i].group(1))
                if url and title:
                    results.append({"title": title, "url": url, "snippet": snippet})

        if not results:
            return f"No search results found for query: '{query}'."

        formatted_items = []
        for idx, item in enumerate(results[:max_results], 1):
            formatted_items.append(
                f"{idx}. **Title**: {item['title']}\n"
                f"   **URL**: {item['url']}\n"
                f"   **Snippet**: {item['snippet']}"
            )
        return "\n\n".join(formatted_items)

    except Exception as e:
        logger.error(f"Error performing web search for '{query}': {e}")
        return f"Error performing web search: {str(e)}"


@tool(category="web")
def fetch_url_content(url: str, max_chars: int = 4000) -> str:
    """Fetches text content from a given URL, strips HTML tags, and truncates to max_chars.

    Args:
        url: The web page URL to fetch content from.
        max_chars: Maximum character length of the returned text (default: 4000).

    Returns:
        Cleaned plain text of the webpage or an error message.
    """
    if not url or not url.strip():
        return "Error: URL cannot be empty."

    target_url = url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    try:
        headers = {"User-Agent": _DEFAULT_USER_AGENT}
        req = urllib.request.Request(target_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "")
            raw_data = response.read()
            charset = "utf-8"
            if "charset=" in content_type.lower():
                try:
                    charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()
                except Exception:
                    charset = "utf-8"
            try:
                raw_text = raw_data.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                raw_text = raw_data.decode("utf-8", errors="replace")

        cleaned_text = _clean_html_text(raw_text)

        if not cleaned_text:
            return "Empty webpage content."

        if len(cleaned_text) > max_chars:
            cleaned_text = cleaned_text[:max_chars].rstrip() + "\n\n... [Content truncated]"

        return cleaned_text

    except Exception as e:
        logger.error(f"Error fetching URL content from '{target_url}': {e}")
        return f"Error fetching URL content: {str(e)}"
