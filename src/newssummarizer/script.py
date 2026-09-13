from __future__ import annotations

import re

from .models import Article, Script, utc_now

TARGET_WORDS = 140


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    sentences = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        sentence = sentence.strip(" \t\n-–")
        if len(sentence.split()) < 5:
            continue
        sentence = sentence[0].upper() + sentence[1:]
        if sentence[-1] not in ".!?":
            sentence += "."
        sentences.append(sentence)
    return sentences


def _first_sentence(article: Article) -> str | None:
    return next(iter(_sentences(article.text)), None)


def make_script(article: Article, perspectives: list[Article]) -> Script:
    """Create a ~60-second, attribution-first script without a hosted model.

    It is intentionally extractive: while offline it uses only cached text and
    never invents details that are absent from those local records.
    """
    sources_with_text = [item for item in [article, *perspectives] if item.text.strip()]
    lead = _first_sentence(article)
    if not lead:
        lead = "The saved sources do not contain enough article text for a factual narration."
    if lead.casefold().startswith(article.publisher.casefold()):
        lead = lead[len(article.publisher):].lstrip(" ,:-")
        lead = lead[0].upper() + lead[1:] if lead else ""

    paragraphs = [f"{lead} This is a developing story, so the details below are attributed to their original reporting."]
    words_used = len(paragraphs[0].split())
    for index, item in enumerate(sources_with_text):
        sentences = _sentences(item.text)
        # The primary source's first sentence is already the lead. Later
        # sentences add context instead of restating the opening.
        candidates = sentences[1:3] if index == 0 else sentences[:2]
        for sentence_index, sentence in enumerate(candidates):
            if sentence.casefold().startswith(item.publisher.casefold()):
                sentence = sentence[len(item.publisher):].lstrip(" ,:-")
                sentence = sentence[0].upper() + sentence[1:] if sentence else ""
            if not sentence:
                continue
            if index == 0:
                paragraph = (f"The same report adds that {sentence[0].lower() + sentence[1:]}"
                             if sentence_index == 0 else f"It also notes that {sentence[0].lower() + sentence[1:]}")
            elif index == 1:
                paragraph = f"Separately, {item.publisher} reports that {sentence[0].lower() + sentence[1:]}"
            else:
                paragraph = f"In additional reporting, {item.publisher} says that {sentence[0].lower() + sentence[1:]}"
            if words_used + len(paragraph.split()) > TARGET_WORDS - 30:
                break
            paragraphs.append(paragraph)
            words_used += len(paragraph.split())

    source_names = ", ".join(dict.fromkeys(item.publisher for item in [article, *perspectives]))
    conclusion = (f"Taken together, these reports provide a broader view, but they do not settle every question. "
                  f"Read the original coverage from {source_names} through the links in the description before drawing conclusions.")
    paragraphs.append(conclusion)
    body = "\n\n".join(paragraphs)
    sources = [{"publisher": article.publisher, "title": article.title, "url": article.url}]
    sources.extend({"publisher": p.publisher, "title": p.title, "url": p.url} for p in perspectives)
    return Script(article_url=article.url, title=article.title, created_at=utc_now(), body=body, sources=sources)


def to_markdown(script: Script) -> str:
    links = "\n".join(f"- [{s['publisher']}: {s['title']}]({s['url']})" for s in script.sources)
    return (f"# YouTube Short script: {script.title}\n\nEstimated narration: about 60 seconds\n\n{script.body}\n\n"
            f"## Original sources\n\n{links}\n\n## Editorial note\n\nThis is a source-attributed comparison, not a guarantee of neutrality. Open the original reporting before publishing.\n")


def quality_signals(script: Script) -> dict[str, int | bool]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", script.body.replace("\n", " ")) if part.strip()]
    return {
        "words": len(script.body.split()),
        "sentences": len(sentences),
        "punctuation_complete": all(part[-1] in ".!?" for part in sentences),
    }
