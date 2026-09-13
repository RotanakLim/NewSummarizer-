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
    sources_with_text = [item for item in [article, *perspectives] if item.text.strip()]
    chosen, count = [], 0
    # Round-robin source selection makes the narration cite more than one
    # outlet when the user has supplied multiple reports.
    for item in sources_with_text:
        for sentence in _sentences(item.text):
            line = f"{item.publisher} reports {sentence}"
            if count + len(line.split()) > TARGET_WORDS - 38:
                break
            chosen.append(line)
            count += len(line.split())
            break
    for sentence in _sentences(article.text):
        line = f"{article.publisher} also reports {sentence}"
        if count + len(line.split()) > TARGET_WORDS - 38:
            break
        if line not in chosen:
            chosen.append(line)
            count += len(line.split())
    if not chosen:
        chosen = ["The saved sources do not contain enough article text for a factual narration."]
    labels = ", ".join(dict.fromkeys(item.publisher for item in [article, *perspectives]))
    body = (f"Here is the source-attributed update on {article.title}. {' '.join(chosen)} "
            f"For other coverage, compare the original reporting from {labels}. "
            "The links are in the description. Separate verified facts from claims, commentary, and analysis before publishing.")
    sources = [{"publisher": article.publisher, "title": article.title, "url": article.url}]
    sources.extend({"publisher": p.publisher, "title": p.title, "url": p.url} for p in perspectives)
    return Script(article_url=article.url, title=article.title, created_at=utc_now(), body=body, sources=sources)


def to_markdown(script: Script) -> str:
    links = "\n".join(f"- [{s['publisher']}: {s['title']}]({s['url']})" for s in script.sources)
    return (f"# YouTube Short script: {script.title}\n\nEstimated narration: about 60 seconds\n\n{script.body}\n\n"
            f"## Original sources\n\n{links}\n\n## Editorial note\n\nThis is a source-attributed comparison, not a guarantee of neutrality. Open the original reporting before publishing.\n")
