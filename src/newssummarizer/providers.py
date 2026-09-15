"""Permission-aware news discovery connectors."""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .models import Article

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRESH_WINDOW_DAYS = 2


def plain_text(value: str) -> str:
    """Convert provider HTML to clean narration text without changing facts."""
    if "<" not in value:
        return value.strip()
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def fresh_window_start() -> str:
    """Return the UTC date two days ago for current-event provider filters."""
    return (datetime.now(timezone.utc) - timedelta(days=FRESH_WINDOW_DAYS)).date().isoformat()


def local_secret(name: str) -> str | None:
    """Read a key from the environment, then the local ignored .env file."""
    if value := os.environ.get(name):
        return value
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return value.strip().strip('"').strip("'") or None
    return None


def save_local_secrets(values: dict[str, str]) -> None:
    """Update only known key names in an ignored local .env file."""
    env_file = PROJECT_ROOT / ".env"
    existing = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                existing[key.strip()] = value.strip()
    existing.update({key: value.strip() for key, value in values.items() if value.strip()})
    safe_lines = [f"{key}={value}" for key, value in existing.items() if key in {"GUARDIAN_API_KEY", "THENEWSAPI_API_TOKEN"}]
    env_file.write_text("\n".join(safe_lines) + "\n", encoding="utf-8")


class ProviderUnavailable(RuntimeError):
    """A source is temporarily unavailable or has rate-limited the request."""


def _collect_text_sources(calls: list[tuple[str, object]]) -> list[Article]:
    """Keep a single provider outage from cancelling an automated run."""
    articles, failures = [], []
    for name, search in calls:
        try:
            articles.extend(search())  # type: ignore[operator]
        except ProviderUnavailable as error:
            failures.append(f"{name}: {error}")
        except httpx.HTTPError:
            failures.append(f"{name}: connection unavailable")
    if not articles and failures:
        detail = "; ".join(failures)
        raise ProviderUnavailable(
            f"Live news sources could not be reached ({detail}). Check your internet connection, then try again."
        )
    return articles


def gdelt_search(query: str, limit: int = 8) -> list[Article]:
    """Discover varied coverage and original links through GDELT DOC 2.0."""
    response = httpx.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
        "query": query, "mode": "artlist", "format": "json", "maxrecords": str(limit),
    }, timeout=25)
    if response.status_code == 429:
        raise ProviderUnavailable("GDELT is rate-limiting requests. Wait a few minutes and try again.")
    response.raise_for_status()
    result, seen_domains = [], set()
    for item in response.json().get("articles", []):
        domain, url = item.get("domain", "Unknown publisher"), item.get("url", "")
        if not url or domain.lower() in seen_domains:
            continue
        seen_domains.add(domain.lower())
        result.append(Article(url=url, title=item.get("title", "Untitled article"), section="general",
                              publisher=domain, published_at=item.get("seendate"), text=""))
        if len(result) == limit:
            break
    return result


def guardian_search(query: str, section: str | None = None, limit: int = 3) -> list[Article]:
    """Get licensed full text from Guardian Open Platform when a key is set."""
    api_key = local_secret("GUARDIAN_API_KEY")
    if not api_key:
        return []
    params = {
        "api-key": api_key, "show-fields": "body", "page-size": str(limit),
        "order-by": "newest", "from-date": fresh_window_start(),
    }
    if query.strip():
        params["q"] = query
    guardian_sections = {
        "world": "world", "business": "business", "environment": "environment",
        "technology": "technology", "artificial intelligence": "technology", "gaming": "culture",
    }
    if section in guardian_sections:
        params["section"] = guardian_sections[section]
    response = httpx.get("https://content.guardianapis.com/search", params=params, timeout=25)
    if response.status_code == 401:
        raise ProviderUnavailable("Guardian rejected the saved API key. Replace it in API setup with a valid, newly rotated key.")
    if response.status_code == 429:
        raise ProviderUnavailable("Guardian is rate-limiting requests. Wait a few minutes and try again.")
    response.raise_for_status()
    return [Article(url=item["webUrl"], title=item["webTitle"], section=item.get("sectionId", "general"),
                    publisher="The Guardian", published_at=item.get("webPublicationDate"),
                    text=plain_text(item.get("fields", {}).get("body", "")))
            for item in response.json()["response"]["results"]]


def thenewsapi_search(query: str, section: str = "general", limit: int = 4) -> list[Article]:
    """Optional multi-publisher summaries from TheNewsAPI.

    The provider returns metadata and a description, so the description is kept
    as attributed source text rather than treated as a full article.
    """
    api_token = local_secret("THENEWSAPI_API_TOKEN")
    if not api_token:
        return []
    category_map = {
        "geopolitics": "politics", "business": "business", "world": "general",
        "environment": "science", "technology": "tech", "artificial intelligence": "tech",
        "gaming": "tech",
    }
    params = {
        "api_token": api_token, "language": "en", "limit": str(limit),
        "categories": category_map.get(section, "general"),
        "published_after": fresh_window_start(), "sort": "published_at",
    }
    if query.strip():
        params["search"] = query
    response = httpx.get("https://api.thenewsapi.com/v1/news/all", params=params, timeout=25)
    if response.status_code == 401:
        raise ProviderUnavailable("TheNewsAPI rejected the saved token. Replace it in API setup or leave that connector blank.")
    if response.status_code == 429:
        raise ProviderUnavailable("TheNewsAPI is rate-limiting requests. Wait a few minutes and try again.")
    response.raise_for_status()
    articles, seen_publishers = [], set()
    for item in response.json().get("data", []):
        publisher = item.get("source", "Unknown publisher")
        if isinstance(publisher, dict):
            publisher = publisher.get("name") or publisher.get("url") or "Unknown publisher"
        if not item.get("url") or publisher.casefold() in seen_publishers:
            continue
        seen_publishers.add(publisher.casefold())
        articles.append(Article(
            url=item["url"], title=item.get("title", query), section="general", publisher=publisher,
            published_at=item.get("published_at"), text=item.get("description") or "",
        ))
    return articles


def discover(query: str, section: str = "general", limit: int = 4) -> tuple[list[Article], list[Article]]:
    scriptable = _collect_text_sources([
        ("Guardian", lambda: guardian_search(query, section, limit=limit)),
        ("TheNewsAPI", lambda: thenewsapi_search(query, section, limit=limit)),
    ])
    try:
        comparisons = gdelt_search(query)
    except (ProviderUnavailable, httpx.HTTPError):
        comparisons = []
    return scriptable, comparisons


def discover_current_category(section: str, limit: int = 15) -> tuple[list[Article], list[Article]]:
    """Return only fresh category coverage, ordered by the providers' publication dates."""
    scriptable = _collect_text_sources([
        ("Guardian", lambda: guardian_search("", section, limit=limit)),
        ("TheNewsAPI", lambda: thenewsapi_search("", section, limit=limit)),
    ])
    try:
        comparisons = gdelt_search(f"{section} news", limit=8)
    except (ProviderUnavailable, httpx.HTTPError):
        comparisons = []
    return scriptable, comparisons
