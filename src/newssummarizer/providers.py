"""Permission-aware news discovery connectors."""
from __future__ import annotations

import os

import httpx

from .models import Article


class ProviderUnavailable(RuntimeError):
    """A source is temporarily unavailable or has rate-limited the request."""


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
    api_key = os.environ.get("GUARDIAN_API_KEY")
    if not api_key:
        return []
    params = {"api-key": api_key, "q": query, "show-fields": "body", "page-size": str(limit)}
    if section and section != "general":
        params["section"] = section
    response = httpx.get("https://content.guardianapis.com/search", params=params, timeout=25)
    response.raise_for_status()
    return [Article(url=item["webUrl"], title=item["webTitle"], section=item.get("sectionId", "general"),
                    publisher="The Guardian", published_at=item.get("webPublicationDate"),
                    text=item.get("fields", {}).get("body", ""))
            for item in response.json()["response"]["results"]]


def discover(query: str, section: str = "general") -> tuple[list[Article], list[Article]]:
    return guardian_search(query, section), gdelt_search(query)
