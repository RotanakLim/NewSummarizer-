from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Article, Script
from .script import to_markdown


class Store:
    """A deliberately simple local cache; no network dependency in read paths."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.articles = root / "articles"
        self.scripts = root / "scripts"
        self.articles.mkdir(parents=True, exist_ok=True)
        self.scripts.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _key(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def save_article(self, article: Article) -> None:
        (self.articles / f"{self._key(article.url)}.json").write_text(
            json.dumps(article.to_dict(), indent=2), encoding="utf-8"
        )

    def all_articles(self, section: str | None = None) -> list[Article]:
        result = []
        for path in self.articles.glob("*.json"):
            article = Article.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if section is None or article.section.lower() == section.lower():
                result.append(article)
        return sorted(result, key=lambda a: a.published_at or "", reverse=True)

    def save_script(self, script: Script) -> Path:
        path = self.scripts / f"{self._key(script.article_url)}.json"
        path.write_text(json.dumps(script.to_dict(), indent=2), encoding="utf-8")
        path.with_suffix(".md").write_text(to_markdown(script), encoding="utf-8")
        return path

    def recent_scripts(self, limit: int = 6) -> list[Script]:
        return self.all_scripts()[:limit]

    def all_scripts(self) -> list[Script]:
        """Return every locally saved script, newest first."""
        scripts = [Script.from_dict(json.loads(path.read_text(encoding="utf-8")))
                   for path in self.scripts.glob("*.json")]
        return sorted(scripts, key=lambda script: script.created_at, reverse=True)
