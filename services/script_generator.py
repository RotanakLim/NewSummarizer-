"""Turns an article's title/summary into a ~60 second YouTube Shorts script
using the Anthropic API."""
from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, SCRIPT_TARGET_WORDS

_PROMPT_TEMPLATE = """You write scripts for YouTube Shorts that summarize news articles.

Turn the article below into a spoken script for a ~60 second video.

Rules:
- Target about {target_words} words (roughly 60 seconds at a brisk speaking pace).
- Open with a hook in the first line that grabs attention, don't just restate the headline.
- Write in short, punchy, spoken sentences meant to be read aloud, not formal written prose.
- Cover only the most important facts from the article; skip minor details.
- End with a short closing line (a takeaway or a light call-to-action), not "click the link".
- Do not include stage directions, camera notes, hashtags, or headings. Output only the spoken script text.

Article title: {title}
Article summary: {summary}
"""


def generate_script(article: dict) -> str:
    """Generate a short-form video script for the given article dict
    (expects 'title' and 'summary' keys). Raises RuntimeError if no API key
    is configured or the API call fails."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or a .env file."
        )

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = _PROMPT_TEMPLATE.format(
        target_words=SCRIPT_TARGET_WORDS,
        title=article.get("title", ""),
        summary=article.get("summary", ""),
    )

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()
