"""Brave Web Search API client wrapper."""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
import json
from typing import Any, Dict, List, Optional


BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_COUNT = 20  # Brave hard limit per request
DEFAULT_RETRY_DELAYS = [2, 5, 10]  # seconds between retries


class BraveSearchError(Exception):
    pass


class BraveSearchClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Brave API key is required")
        self._api_key = api_key

    def search(
        self,
        q: str,
        count: int = 10,
        freshness: Optional[str] = None,
        safesearch: str = "strict",
        country: str = "US",
        search_lang: str = "en",
        result_filter: Optional[str] = None,
        retry_delays: List[int] = DEFAULT_RETRY_DELAYS,
    ) -> List[Dict[str, Any]]:
        """Run a Brave web search and return normalized candidate list."""
        count = min(count, MAX_COUNT)
        params: Dict[str, str] = {
            "q": q[:400],  # Brave query max: 400 chars
            "count": str(count),
            "safesearch": safesearch,
            "country": country,
            "search_lang": search_lang,
            "text_decorations": "false",
            "extra_snippets": "false",
        }
        if freshness:
            params["freshness"] = freshness
        if result_filter:
            params["result_filter"] = result_filter

        url = f"{BRAVE_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }

        last_error: Optional[Exception] = None
        attempts = [0] + list(retry_delays)
        for attempt, delay in enumerate(attempts):
            if delay > 0:
                time.sleep(delay)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    # Handle gzip if needed
                    if resp.info().get("Content-Encoding") == "gzip":
                        import gzip
                        raw = gzip.decompress(raw)
                    data = json.loads(raw.decode("utf-8"))
                return _normalize_results(data)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 503) and attempt < len(retry_delays):
                    last_error = exc
                    continue
                raise BraveSearchError(f"Brave API HTTP {exc.code}: {exc.reason}") from exc
            except urllib.error.URLError as exc:
                if attempt < len(retry_delays):
                    last_error = exc
                    continue
                raise BraveSearchError(f"Brave API network error: {exc.reason}") from exc

        raise BraveSearchError(f"Brave API failed after {len(attempts)} attempts: {last_error}") from last_error


def _normalize_results(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract web results into a flat normalized list."""
    candidates = []
    web = data.get("web", {})
    results = web.get("results", [])
    for r in results:
        url = r.get("url", "")
        domain = _extract_domain(url)
        candidates.append({
            "title": r.get("title", "").strip(),
            "url": url,
            "domain": domain,
            "snippet": r.get("description", "").strip(),
            "source": r.get("profile", {}).get("name", "") or domain,
            "published_at": r.get("age") or r.get("page_fetched"),
            "query_source": None,  # caller fills this in
        })
    return candidates


def _extract_domain(url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc.lstrip("www.")
    except Exception:
        return ""
