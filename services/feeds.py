"""Fetching and parsing Reuters RSS feeds."""
import hashlib
import re

import feedparser

from config import CATEGORY_FEEDS

# In-memory cache so an article picked from a listing page can be looked up
# again by id when the user opens it, without re-fetching the whole feed.
_ARTICLE_CACHE: dict[str, dict] = {}


def _make_id(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def get_articles(category: str, limit: int = 20) -> list[dict]:
    """Fetch and parse the RSS feed for a category, returning a list of
    lightweight article dicts. Raises ValueError for an unknown category and
    RuntimeError if the feed can't be fetched or parsed."""
    feed_url = CATEGORY_FEEDS.get(category)
    if not feed_url:
        raise ValueError(f"Unknown category: {category}")

    parsed = feedparser.parse(feed_url)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"Could not load feed for '{category}': {parsed.bozo_exception}")

    articles = []
    for entry in parsed.entries[:limit]:
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        article = {
            "id": _make_id(link),
            "title": entry.get("title", "Untitled"),
            "link": link,
            "summary": summary,
            "published": entry.get("published", ""),
            "category": category,
        }
        _ARTICLE_CACHE[article["id"]] = article
        articles.append(article)

    return articles


def get_article(article_id: str) -> dict | None:
    """Look up a previously fetched article by id. Returns None if it isn't
    in the cache (e.g. the app restarted or the feed was never loaded)."""
    return _ARTICLE_CACHE.get(article_id)
