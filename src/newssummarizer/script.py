from __future__ import annotations

import re

from .models import Article, Script, utc_now

TARGET_WORDS = 260
MIN_PRIMARY_SOURCE_WORDS = 80


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


def _audience_ready_sentences(text: str) -> list[str]:
    """Keep complete, audience-facing factual sentences; drop quote fragments."""
    fragments = ("and ", "but ", "because ", "of ", "that ", "to ", "which ", "while ")
    usable = []
    for sentence in _sentences(text):
        lower = sentence.casefold().lstrip("“\"'")
        words = sentence.split()
        if len(words) < 8 or lower.startswith(fragments):
            continue
        # Isolated first-person quotations and attribution fragments rarely
        # explain a story to a listener without their surrounding paragraph.
        if sentence.lstrip().startswith(("“", '"', "'")) and re.search(r"\b(i|we|my|our)\b", lower):
            continue
        if re.search(r"\b(i|we|my|our)\b", lower) and ("said" in lower or "told" in lower):
            continue
        usable.append(sentence)
    return usable


def _first_sentence(article: Article) -> str | None:
    return next(iter(_audience_ready_sentences(article.text)), None)


def narration_ready(article: Article) -> bool:
    """Require enough provider-supplied text for a full factual narration."""
    return (len(article.text.split()) >= MIN_PRIMARY_SOURCE_WORDS
            and len(_audience_ready_sentences(article.text)) >= 3)


def make_script(article: Article, perspectives: list[Article]) -> Script:
    """Create a compact, detailed attribution-first explainer without a hosted model.

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
    if not lead:
        lead = "The available report describes a developing story."

    paragraphs = [f"According to {article.publisher}, {lead[0].lower() + lead[1:]}"]
    words_used = len(paragraphs[0].split())
    context_added = False
    for index, item in enumerate(sources_with_text):
        sentences = _audience_ready_sentences(item.text)
        # The primary source's first sentence is already the lead. Take a
        # fuller run of subsequent sentences so background, consequences, and
        # prior context included by the reporter are not discarded.
        candidates = sentences[1:9] if index == 0 else sentences[:5]
        for sentence_index, sentence in enumerate(candidates):
            if sentence.casefold().startswith(item.publisher.casefold()):
                sentence = sentence[len(item.publisher):].lstrip(" ,:-")
                sentence = sentence[0].upper() + sentence[1:] if sentence else ""
            if not sentence:
                continue
            if index == 0:
                lower = sentence.casefold()
                if not context_added and any(marker in lower for marker in ("previous", "earlier", "before ", "after ", "years ago", "history")):
                    paragraph = f"For context, {sentence[0].lower() + sentence[1:]}"
                    context_added = True
                elif sentence_index == 0:
                    paragraph = f"The report also explains that {sentence[0].lower() + sentence[1:]}"
                else:
                    # A complete reported sentence is clearer than repeatedly
                    # wrapping every detail in the same template phrase.
                    paragraph = sentence
            elif index == 1:
                paragraph = (f"A separate report from {item.publisher} adds that {sentence[0].lower() + sentence[1:]}"
                             if sentence_index == 0 else sentence)
            else:
                paragraph = (f"{item.publisher} also reports that {sentence[0].lower() + sentence[1:]}"
                             if sentence_index == 0 else sentence)
            if words_used + len(paragraph.split()) > TARGET_WORDS - 35:
                break
            paragraphs.append(paragraph)
            words_used += len(paragraph.split())

    source_names = ", ".join(dict.fromkeys(item.publisher for item in [article, *perspectives]))
    conclusion = (f"Taken together, these reports provide a broader view, but they do not settle every question. "
                  f"Read the original coverage from {source_names} through the links in the description before drawing conclusions.")
    paragraphs.append(conclusion)
    body = "\n\n".join(paragraphs)
    sources = [{"publisher": article.publisher, "title": article.title, "url": article.url,
                "published_at": article.published_at or ""}]
    sources.extend({"publisher": p.publisher, "title": p.title, "url": p.url,
                    "published_at": p.published_at or ""} for p in perspectives)
    return Script(article_url=article.url, title=article.title, created_at=utc_now(), body=body, sources=sources)


def to_markdown(script: Script) -> str:
    links = "\n".join(f"- [{s['publisher']}: {s['title']}]({s['url']})" for s in script.sources)
    return (f"# Video script: {script.title}\n\nEstimated narration: compact detailed explainer, typically 1–2 minutes\n\n{script.body}\n\n"
            f"## Original sources\n\n{links}\n\n## Editorial note\n\nThis is a source-attributed comparison, not a guarantee of neutrality. Open the original reporting before publishing.\n")


def quality_signals(script: Script) -> dict[str, int | bool]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", script.body.replace("\n", " ")) if part.strip()]
    return {
        "words": len(script.body.split()),
        "sentences": len(sentences),
        "punctuation_complete": all(part[-1] in ".!?" for part in sentences),
    }
