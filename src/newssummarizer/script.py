from __future__ import annotations

import re

from .models import Article, Script, utc_now

TARGET_WORDS = 140


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 4]


def make_script(article: Article, perspectives: list[Article]) -> Script:
    """Create a ~60-second, attribution-first script without a hosted model.

    It is intentionally extractive: while offline it uses only cached text and
    never invents details that are absent from those local records.
    """
    chosen: list[str] = []
    count = 0
    for sentence in _sentences(article.text):
        if count + len(sentence.split()) > TARGET_WORDS - 55:
            break
        chosen.append(sentence)
        count += len(sentence.split())
    if not chosen:
        chosen = ["This source is included as a headline and link, not as enough licensed full text to narrate its details."]
    extra = ""
    if perspectives:
        labels = ", ".join(p.publisher for p in perspectives[:4])
        extra = f" To compare coverage, review original reporting from {labels}. Those links are included below; their presence does not mean they agree with every claim."
    body = (f"Here is the source-attributed update on {article.title}. According to {article.publisher}: "
            f"{' '.join(chosen)}{extra} Before sharing, check the source links and distinguish verified facts from claims or analysis.")
    sources = [{"publisher": article.publisher, "title": article.title, "url": article.url}]
    sources.extend({"publisher": p.publisher, "title": p.title, "url": p.url} for p in perspectives)
    return Script(article_url=article.url, title=article.title, created_at=utc_now(), body=body, sources=sources)


def to_markdown(script: Script) -> str:
    links = "\n".join(f"- [{s['publisher']}: {s['title']}]({s['url']})" for s in script.sources)
    return (f"# YouTube Short script: {script.title}\n\nEstimated narration: about 60 seconds\n\n{script.body}\n\n"
            f"## Original sources\n\n{links}\n\n## Editorial note\n\nThis is a source-attributed comparison, not a guarantee of neutrality. Open the original reporting before publishing.\n")
