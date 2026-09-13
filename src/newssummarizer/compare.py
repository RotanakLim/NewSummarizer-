from __future__ import annotations

import httpx

from .models import Article


def corroborating_articles(article: Article, limit: int = 3) -> list[Article]:
    """Find independently-published coverage through GDELT's public Doc API.

    This is an online-only retrieval step. Results are candidates, not a claim
    that every outlet is independent or that its account is correct.
    """
    query = " ".join(article.title.split()[:12])
    params = {"query": query, "mode": "artlist", "format": "json", "maxrecords": str(limit * 3)}
    response = httpx.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=25)
    response.raise_for_status()
    results: list[Article] = []
    for item in response.json().get("articles", []):
        source = item.get("domain", "Unknown")
        url = item.get("url", "")
        if not url or "reuters.com" in source.lower():
            continue
        results.append(Article(url=url, title=item.get("title", "Untitled"), section=article.section,
                               publisher=source, published_at=item.get("seendate"), text=""))
        if len(results) == limit:
            break
    return results
