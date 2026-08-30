import re
import urllib.request
import urllib.parse
import json
from orchestration.tools.registry import tool

@tool(category='web')
def web_search(query: str, max_results: int = 5) -> str:
    """Searches the web using DuckDuckGo and returns titles, snippets, and URLs."""
    try:
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            'https://lite.duckduckgo.com/lite/',
            data=data,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        
        snippets = re.findall(r'class=[\'"]result-snippet[\'"]>(.*?)</td>', html, flags=re.DOTALL)
        links = re.findall(r'<a[^>]+class=[\'"]result-link[\'"][^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', html, flags=re.DOTALL)
        
        results = []
        for i in range(min(max_results, len(snippets))):
            sn = re.sub(r'<[^>]+>', '', snippets[i]).strip()
            title = re.sub(r'<[^>]+>', '', links[i][1]).strip() if i < len(links) else f"Result {i+1}"
            url = links[i][0] if i < len(links) else ""
            results.append(f"{i+1}. **{title}**\n   {sn}\n   URL: {url}")
        
        if not results:
            results.append(f"No direct snippets found for: {query}.")
        return '\n\n'.join(results)
    except Exception as e:
        return f"Web search error: {e}"

@tool(category='web')
def fetch_url_content(url: str, max_chars: int = 4000) -> str:
    """Fetches and extracts text from a given HTTP/HTTPS URL."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) > max_chars:
            return text[:max_chars] + f'\n... (truncated at {max_chars} chars)'
        return text if text else 'No readable text found at URL.'
    except Exception as e:
        return f'Error fetching URL {url}: {e}'
