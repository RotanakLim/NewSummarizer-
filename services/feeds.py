"""Fetching and parsing Reuters RSS feeds."""
import re
import urllib.error
import urllib.request

import feedparser

from config import CATEGORY_FEEDS

# Control characters that are illegal inside XML 1.0 documents. Some feeds
# include them (e.g. in a headline or summary) which makes strict XML
# parsers choke with "not well-formed (invalid token)" even though the rest
# of the document is fine, so they're stripped out before parsing.
_INVALID_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

_REQUEST_HEADERS = {
    # Some feed hosts reject the default urllib/feedparser user agent.
    "User-Agent": (
        "Mozilla/5.0 (compatible; NewSummarizerBot/1.0; "
        "+https://github.com/RotanakLim/NewSummarizer-)"
    )
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_feed_bytes(feed_url: str) -> bytes:
    request = urllib.request.Request(feed_url, headers=_REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach feed at {feed_url}: {exc}") from exc


def get_articles(category: str, limit: int = 20) -> list[dict]:
    """Fetch and parse the RSS feed for a category, returning a list of
    lightweight article dicts. Raises ValueError for an unknown category and
    RuntimeError if the feed can't be fetched or parsed."""
    feed_url = CATEGORY_FEEDS.get(category)
    if not feed_url:
        raise ValueError(f"Unknown category: {category}")

    raw = _fetch_feed_bytes(feed_url)
    cleaned = _INVALID_XML_CHARS_RE.sub("", raw.decode("utf-8", errors="replace"))

    parsed = feedparser.parse(cleaned)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Could not load feed for '{category}': {parsed.bozo_exception}")

    articles = []
    for entry in parsed.entries[:limit]:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        article = {
            "title": entry.get("title", "Untitled"),
            "link": link,
            "summary": summary,
            "published": entry.get("published", ""),
            "category": category,
        }
        articles.append(article)

    return articles
