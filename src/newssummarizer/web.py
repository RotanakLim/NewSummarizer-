from __future__ import annotations

import html
import hashlib
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .models import Article, Script
from .providers import ProviderUnavailable, discover, discover_current_category, local_secret, plain_text, save_local_secrets
from .script import make_script, narration_ready, quality_signals, to_markdown
from .store import Store

PAGE = """<!doctype html><html><head><meta charset=\"utf-8\"><title>News Summarizer</title><style>
:root{font-family:ui-sans-serif,system-ui;color:#152231;background:#f6f7f8}body{max-width:1040px;margin:0 auto;padding:28px 20px 72px}.top{display:flex;justify-content:space-between;align-items:end;gap:20px;border-bottom:1px solid #d8dee4;padding-bottom:18px}h1{margin:0;font-size:30px}h2{margin:24px 0 10px}h3{margin:15px 0 8px}.muted,small{color:#5a6773}.notice{background:#e8f3ff;border-left:4px solid #0b6fb6;padding:13px 15px;margin:20px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.card{background:#fff;border:1px solid #d8dee4;border-radius:8px;padding:16px;margin-top:16px}.source{background:#fff;border:1px solid #d8dee4;border-radius:8px;padding:14px;margin-top:12px}label{display:block;font-weight:650;margin:8px 0 3px}input,select,textarea{width:100%;box-sizing:border-box;border:1px solid #aab6c0;border-radius:5px;padding:9px;font:inherit}textarea{height:115px}textarea.narration{height:300px;background:#fff;color:#152231;line-height:1.55;resize:vertical}button{background:#e65f17;color:#fff;border:0;border-radius:5px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer;margin:12px 8px 0 0}.secondary{background:#34495e}.stats{display:flex;gap:10px;flex-wrap:wrap}.stat{background:#edf1f4;border-radius:5px;padding:8px 12px}.stat b{font-size:20px;display:block}.source a{color:#075985;overflow-wrap:anywhere}.past-link{position:fixed;left:18px;bottom:18px;background:#34495e;color:#fff;text-decoration:none;border-radius:6px;padding:11px 14px;font-weight:700;box-shadow:0 2px 8px #0003}@media(max-width:600px){body{padding:18px 12px}.top{align-items:start;flex-direction:column}.past-link{left:12px;bottom:12px}}
</style></head><body><header class=\"top\"><div><h1>News Summarizer</h1><div class=\"muted\">Source-attributed scripts for YouTube Shorts</div></div><div class=\"muted\">Local-first · No publishing from this app</div></header>
<div class=\"notice\"><b>Editorial standard:</b> automate collection, retain every original link, and review claims before publishing. Source diversity improves context; it does not prove a script is neutral.</div>
<details class=\"card\"><summary><b>API setup</b> — required for fully automated scripts</summary><p class=\"muted\">Keys are saved only to this computer in an ignored <code>.env</code> file. They are never shown again in this app. Use a newly rotated Guardian key if an earlier key was exposed.</p><form method=\"post\"><input type=\"hidden\" name=\"action\" value=\"configure\"><label>Guardian API key</label><input type=\"password\" name=\"guardian_key\" autocomplete=\"off\" placeholder=\"Paste a replacement key\"><label>TheNewsAPI token (optional)</label><input type=\"password\" name=\"thenewsapi_token\" autocomplete=\"off\" placeholder=\"Optional multi-publisher connector\"><button>Save local API setup</button></form><small>Configured: Guardian __GUARDIAN_STATUS__ · TheNewsAPI __THENEWS_STATUS__</small></details>
<section class=\"card\"><h2>Generate a current-events briefing</h2><p class=\"muted\">Choose one category. The app searches only coverage published in the last two days, skips articles already used in your scripts, and creates a compact, detailed explainer for each distinct story it can support.</p><form method=\"post\"><input type=\"hidden\" name=\"action\" value=\"category\"><div class=\"grid\"><div><label>Category</label><select name=\"section\"><option>general</option><option>geopolitics</option><option>business</option><option>world</option><option>environment</option><option>technology</option><option>artificial intelligence</option><option>gaming</option></select></div><div><label>Scripts to create</label><select name=\"script_count\"><option>2</option><option selected>3</option><option>4</option><option>5</option></select><small>Scripts usually run about 1–2 minutes when sources support it. The app keeps relevant background and context from the article, rotates publishers when available, and will not reuse an earlier script.</small></div></div><button>Generate current scripts</button></form><form method=\"post\"><input type=\"hidden\" name=\"action\" value=\"demo\"><button class=\"secondary\">Run test preview</button><small>Uses clearly labelled sample reporting and placeholder links—no API key or network request required.</small></form></section>
<details class=\"card\"><summary><b>Advanced: create from saved source text</b></summary><p class=\"muted\">Use this only when material is not available through the configured automated sources.</p><form method=\"post\"><input type=\"hidden\" name=\"action\" value=\"draft\"><label>Topic / script headline</label><input name=\"topic\" required placeholder=\"What happened?\"><div class=\"grid\">__SOURCE_1____SOURCE_2____SOURCE_3__</div><button>Generate from saved sources</button></form></details>
__RESULT__
<a class="past-link" href="/scripts">Past scripts</a><script>function copyScript(id){const value=document.getElementById(id).value;navigator.clipboard.writeText(value);document.getElementById(id+'-status').textContent='Copied.'}</script></body></html>"""

PAST_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Past scripts · News Summarizer</title><style>
:root{font-family:ui-sans-serif,system-ui;color:#152231;background:#f6f7f8}body{max-width:1040px;margin:0 auto;padding:28px 20px 72px}h1{margin:0;font-size:30px}h2{margin:0 0 8px}.muted,small{color:#5a6773}.card{background:#fff;border:1px solid #d8dee4;border-radius:8px;padding:16px;margin-top:16px}textarea{width:100%;box-sizing:border-box;border:1px solid #aab6c0;border-radius:5px;padding:10px;font:inherit;line-height:1.55;height:300px;resize:vertical;margin-top:8px}.sources{padding-left:20px}.sources a{color:#075985;overflow-wrap:anywhere}button{background:#e65f17;color:#fff;border:0;border-radius:5px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer;margin-top:12px}.home-link{position:fixed;left:18px;bottom:18px;background:#34495e;color:#fff;text-decoration:none;border-radius:6px;padding:11px 14px;font-weight:700;box-shadow:0 2px 8px #0003}@media(max-width:600px){body{padding:18px 12px}.home-link{left:12px;bottom:12px}}\n+</style></head><body><header><h1>Past scripts</h1><p class="muted">Every locally saved narration, newest first.</p></header>__SCRIPTS__<a class="home-link" href="/">Back to generator</a><script>function copyScript(id){navigator.clipboard.writeText(document.getElementById(id).value);document.getElementById(id+'-status').textContent='Copied.'}</script></body></html>"""


def source_fields(number: int, required: bool = False) -> str:
    note = "Primary narration source" if number == 1 else "Comparison source (optional)"
    required_attr = " required" if required else ""
    return f"""<div class=\"source\"><h3>Source {number}</h3><small>{note}</small>
    <label>Publisher</label><input name=\"publisher_{number}\"{required_attr} placeholder=\"e.g. Reuters\">
    <label>Original URL</label><input name=\"url_{number}\"{required_attr} placeholder=\"https://…\">
    <label>Article text</label><textarea name=\"text_{number}\"{required_attr} placeholder=\"Paste allowed article text…\"></textarea></div>"""


def fields_to_articles(fields: dict[str, list[str]], topic: str) -> list[Article]:
    articles = []
    for number in range(1, 4):
        publisher = fields.get(f"publisher_{number}", [""])[0].strip()
        url = fields.get(f"url_{number}", [""])[0].strip()
        text = fields.get(f"text_{number}", [""])[0].strip()
        if not any((publisher, url, text)):
            continue
        if not all((publisher, url, text)):
            raise ValueError(f"Source {number} needs a publisher, original URL, and article text—or leave all three blank.")
        articles.append(Article(url=url, title=topic, section="manual", publisher=publisher, text=text))
    if not articles:
        raise ValueError("Add at least one complete source.")
    return articles


def source_card(article: Article) -> str:
    words = len(article.text.split())
    date = article.published_at.split("T", 1)[0] if article.published_at else "date unavailable"
    return f'<div class="source"><b>{html.escape(article.publisher)}</b> · Published {html.escape(date)} · {words} saved words<br><a target="_blank" href="{html.escape(article.url, quote=True)}">Read original article</a></div>'


def draft_result(script: Script, articles: list[Article]) -> str:
    publishers = len({item.publisher.casefold() for item in articles})
    status = "Ready for editorial review" if publishers >= 2 else "Add another publisher for broader context"
    quality = quality_signals(script)
    sources = "".join(source_card(item) for item in articles)
    markdown = html.escape(to_markdown(script))
    punctuation = "Complete" if quality["punctuation_complete"] else "Review needed"
    script_id = f"script-{hashlib.sha1(script.article_url.encode()).hexdigest()[:12]}"
    primary_date = articles[0].published_at.split("T", 1)[0] if articles[0].published_at else "date unavailable"
    return f"""<section class=\"card\"><h2>{html.escape(script.title)}</h2><p class=\"muted\">Primary article published: {html.escape(primary_date)} · review the narration and source links before publishing.</p><div class=\"stats\"><div class=\"stat\"><b>{len(articles)}</b>sources</div><div class=\"stat\"><b>{publishers}</b>publishers</div><div class=\"stat\"><b>~{quality["words"] // 2}</b>seconds</div><div class=\"stat\"><b>{quality["sentences"]}</b>sentences</div><div class=\"stat\"><b>{punctuation}</b>punctuation</div><div class=\"stat\"><b>{html.escape(status)}</b></div></div><label for=\"{script_id}\">Narration</label><textarea class=\"narration\" id=\"{script_id}\" readonly>{html.escape(plain_text(script.body))}</textarea><button type=\"button\" onclick=\"copyScript('{script_id}')\">Copy script</button><span id=\"{script_id}-status\" class=\"muted\"></span><h3>Source links for description</h3>{sources}<details><summary>View Markdown export</summary><textarea class=\"narration\" readonly>{markdown}</textarea></details></section>"""


def _unique_articles(articles: list[Article]) -> list[Article]:
    unique, seen = [], set()
    for article in articles:
        key = (article.url.casefold(), article.title.casefold())
        if key not in seen and article.text.strip():
            unique.append(article)
            seen.add(key)
    return unique


def _is_current(article: Article) -> bool:
    if not article.published_at:
        return False
    try:
        published = datetime.fromisoformat(article.published_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return published >= datetime.now(timezone.utc) - timedelta(days=2)


def _title_terms(title: str) -> set[str]:
    ignored = {"the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "from", "as", "at"}
    return {term for term in re.findall(r"[a-z0-9]{3,}", title.casefold()) if term not in ignored}


def _is_distinct_story(article: Article, prior_titles: set[str]) -> bool:
    unsuitable = ("live", "league table", "crossword", "quiz", "podcast", "as it happened", "minute by minute")
    title = article.title.casefold()
    if any(phrase in title for phrase in unsuitable):
        return False
    terms = _title_terms(article.title)
    for old_title in prior_titles:
        old_terms = _title_terms(old_title)
        if terms and old_terms and len(terms & old_terms) / min(len(terms), len(old_terms)) >= 0.7:
            return False
    return True


def _choose_fresh_articles(store: Store, articles: list[Article], count: int) -> list[Article]:
    prior_scripts = store.all_scripts()
    used_urls = {script.article_url for script in prior_scripts}
    used_titles = {script.title.casefold() for script in prior_scripts}
    available = [article for article in _unique_articles(articles)
                 if _is_current(article) and narration_ready(article)
                 and article.url not in used_urls and article.title.casefold() not in used_titles
                 and _is_distinct_story(article, used_titles)]
    # First show one current article per publisher; only then use a second
    # article from a publisher when the configured connectors have no diversity.
    selected, publishers = [], set()
    for article in available:
        publisher = article.publisher.casefold()
        if publisher not in publishers:
            selected.append(article)
            publishers.add(publisher)
        if len(selected) == count:
            return selected
    for article in available:
        if article not in selected:
            selected.append(article)
        if len(selected) == count:
            break
    return selected


def category_result(store: Store, section: str, script_count: int) -> str:
    """Turn a category feed into one script per distinct source article."""
    text_sources, comparison_links = discover_current_category(section, limit=15)
    candidates = _choose_fresh_articles(store, text_sources, script_count)
    for article in [*text_sources, *comparison_links]:
        store.save_article(article)
    if not candidates:
        return ('<section class="card"><b>No new current articles included enough licensed text for a full script.</b> '
                'The app searches only the last two days and skips previously used, near-duplicate, live-blog, and ranking stories. Try another category later or add another full-text provider.</section>')
    results = []
    for article in candidates:
        # Links without saved text are displayed for context but never narrated.
        related = comparison_links[:6]
        script = make_script(article, related)
        store.save_script(script)
        results.append(draft_result(script, [article, *related]))
    return (f'<section class="card"><h2>Category briefing complete</h2><p class="muted">Created {len(candidates)} '
            f'script(s) from the last two days of {html.escape(section)} coverage. Previously used articles were skipped, and publishers were rotated where available.</p></section>' + "".join(results))


def demo_result(store: Store) -> str:
    """Offline preview that demonstrates the output without masquerading as news."""
    samples = [
        ("Sample: transit agency opens a new rail extension", "A demonstration transit agency opened a new rail extension on Monday after years of construction. The sample project connects three neighborhoods and adds stations designed for wheelchair access.", "Riders will be able to transfer between the new line and two existing routes. Officials said they will monitor crowding and adjust service after the first month."),
        ("Sample: city launches a community solar program", "A demonstration city launched a community solar program intended to let renters subscribe to a shared array. The sample plan says participants receive bill credits based on the electricity produced.", "Enrollment rules and the size of the credits have not been finalized. Consumer advocates said clear pricing information will be important before applications open."),
        ("Sample: local university tests a flood warning tool", "A demonstration university began testing a flood warning tool that combines rainfall gauges with neighborhood alerts. The sample system is intended to give residents more time to move vehicles and avoid low-lying roads.", "The trial will compare automated alerts with reports from emergency managers. Researchers said the tool will need testing across several storms before it can be evaluated."),
    ]
    results = []
    for index, (title, primary_text, comparison_text) in enumerate(samples, start=1):
        primary = Article(url=f"https://example.com/demo/{index}-primary", title=title, section="demo", publisher="Example Daily", published_at=f"2026-09-{10 + index:02d}T09:00:00Z", text=primary_text)
        comparison = Article(url=f"https://example.com/demo/{index}-comparison", title=title, section="demo", publisher="Example Regional Report", published_at=f"2026-09-{10 + index:02d}T11:00:00Z", text=comparison_text)
        for article in (primary, comparison):
            store.save_article(article)
        script = make_script(primary, [comparison])
        store.save_script(script)
        results.append(draft_result(script, [primary, comparison]))
    return '<section class="card"><h2>Test preview</h2><p class="muted">These are fictional demonstration sources with placeholder links, included only to show the final layout and script quality. They are not real reporting.</p></section>' + "".join(results)


def script_history_card(script: Script) -> str:
    script_id = f"saved-{hashlib.sha1(script.article_url.encode()).hexdigest()[:12]}"
    primary_date = next((source.get("published_at", "") for source in script.sources if source.get("url") == script.article_url), "")
    primary_date = primary_date.split("T", 1)[0] if primary_date else "date unavailable"
    links = "".join(
        f'<li><a href="{html.escape(source["url"], quote=True)}" target="_blank">{html.escape(source["publisher"])}: {html.escape(source["title"])}</a> · Published {html.escape(source.get("published_at", "").split("T", 1)[0] or "date unavailable")}</li>'
        for source in script.sources
    )
    return f'''<section class="card"><h2>{html.escape(script.title)}</h2><small>Article published: {html.escape(primary_date)} · Saved {html.escape(script.created_at)}</small><label for="{script_id}">Narration</label><textarea id="{script_id}" readonly>{html.escape(plain_text(script.body))}</textarea><button type="button" onclick="copyScript('{script_id}')">Copy script</button> <small id="{script_id}-status"></small><h3>Original sources</h3><ul class="sources">{links}</ul></section>'''


def render_scripts(store: Store) -> str:
    scripts = [script for script in store.all_scripts() if not script.title.casefold().startswith("sample:")]
    content = "".join(script_history_card(script) for script in scripts)
    if not content:
        content = '<section class="card"><p class="muted">No scripts have been saved yet. Generate a category briefing or run the test preview first.</p></section>'
    return PAST_PAGE.replace("__SCRIPTS__", content)


def render(store: Store, result: str = "") -> str:
    guardian = "saved" if local_secret("GUARDIAN_API_KEY") else "not configured"
    thenewsapi = "saved" if local_secret("THENEWSAPI_API_TOKEN") else "not configured"
    return PAGE.replace("__SOURCE_1__", source_fields(1, True)).replace("__SOURCE_2__", source_fields(2)).replace("__SOURCE_3__", source_fields(3)).replace("__GUARDIAN_STATUS__", guardian).replace("__THENEWS_STATUS__", thenewsapi).replace("__RESULT__", result)


def serve(data_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    store = Store(data_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send(render_scripts(store) if self.path.rstrip("/") == "/scripts" else render(store))

        def do_POST(self) -> None:  # noqa: N802
            fields = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            try:
                action = fields.get("action", [""])[0]
                if action == "configure":
                    save_local_secrets({
                        "GUARDIAN_API_KEY": fields.get("guardian_key", [""])[0],
                        "THENEWSAPI_API_TOKEN": fields.get("thenewsapi_token", [""])[0],
                    })
                    result = '<section class="card"><b>Local API setup saved.</b> You can now run automated searches without restarting the app.</section>'
                elif action == "category":
                    result = category_result(
                        store,
                        fields.get("section", ["general"])[0],
                        int(fields.get("script_count", ["3"])[0]),
                    )
                elif action == "demo":
                    result = demo_result(store)
                else:
                    topic = fields["topic"][0].strip()
                    articles = fields_to_articles(fields, topic)
                    for article in articles:
                        store.save_article(article)
                    script = make_script(articles[0], articles[1:])
                    store.save_script(script)
                    result = draft_result(script, articles)
            except ProviderUnavailable as error:
                result = f'<section class="card"><b>Automatic discovery is temporarily unavailable:</b> {html.escape(str(error))}</section>'
            except (KeyError, ValueError) as error:
                result = f'<section class="card"><b>Could not complete that request:</b> {html.escape(str(error))}</section>'
            except Exception as error:
                result = f'<section class="card"><b>Source lookup failed:</b> {html.escape(type(error).__name__)}. Use saved source text or try again later.</section>'
            self._send(render(store, result))

        def _send(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    print(f"News Summarizer is running at http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
