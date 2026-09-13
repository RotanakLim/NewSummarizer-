from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
import trafilatura
from bs4 import BeautifulSoup

from .models import Article

HEADERS = {"User-Agent": "NewSummarizer/0.1 (personal research tool)"}


class SourceAccessError(RuntimeError):
    """Raised when a publisher does not allow normal programmatic retrieval."""


def reuters_section_urls(section: str, limit: int = 10) -> list[str]:
    """Retrieve story links from a public Reuters section page.

    This deliberately downloads only ordinary public HTML and does not bypass
    paywalls, logins, or access controls. Check Reuters' terms before bulk use.
    """
    section = section.strip().lower()
    response = httpx.get(f"https://www.reuters.com/{section}/", headers=HEADERS, timeout=20)
    if response.status_code in {401, 403}:
        raise SourceAccessError(
            "Reuters rejected this programmatic request. Do not bypass its access controls; "
            "use an approved Reuters feed/API, or import articles you have lawfully saved."
        )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    for link in soup.select("a[href]"):
        url = urljoin("https://www.reuters.com", link["href"])
        if re.match(r"https://www\.reuters\.com/.+\d{4}-\d{2}-\d{2}/?$", url) and url not in urls:
            urls.append(url)
            if len(urls) >= limit:
                break
    return urls


def fetch_article(url: str, section: str, publisher: str = "Reuters") -> Article:
    response = httpx.get(url, headers=HEADERS, timeout=25, follow_redirects=True)
    if response.status_code in {401, 403}:
        raise SourceAccessError(
            "Reuters rejected this programmatic request. Import a lawfully saved copy instead."
        )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    title = (soup.find("meta", property="og:title") or {}).get("content") or soup.title.get_text(strip=True)
    published = (soup.find("meta", property="article:published_time") or {}).get("content")
    text = trafilatura.extract(response.text, include_comments=False, include_tables=False) or ""
    return Article(url=url, title=title, section=section, publisher=publisher, published_at=published, text=text)


def import_article(path: str, url: str, title: str, section: str, publisher: str = "Reuters") -> Article:
    """Add a text file the user has already saved and is authorized to process."""
    from pathlib import Path

    return Article(url=url, title=title, section=section, publisher=publisher,
                   text=Path(path).read_text(encoding="utf-8"))
