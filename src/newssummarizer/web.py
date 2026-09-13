from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .models import Article, Script
from .providers import ProviderUnavailable, discover
from .script import make_script, to_markdown
from .store import Store

PAGE = """<!doctype html><html><head><meta charset=\"utf-8\"><title>News Summarizer</title><style>
:root{font-family:ui-sans-serif,system-ui;color:#152231;background:#f6f7f8}body{max-width:1040px;margin:0 auto;padding:28px 20px 72px}.top{display:flex;justify-content:space-between;align-items:end;gap:20px;border-bottom:1px solid #d8dee4;padding-bottom:18px}h1{margin:0;font-size:30px}h2{margin:24px 0 10px}h3{margin:15px 0 8px}.muted,small{color:#5a6773}.notice{background:#e8f3ff;border-left:4px solid #0b6fb6;padding:13px 15px;margin:20px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}.card{background:#fff;border:1px solid #d8dee4;border-radius:8px;padding:16px;margin-top:16px}.source{background:#fff;border:1px solid #d8dee4;border-radius:8px;padding:14px;margin-top:12px}label{display:block;font-weight:650;margin:8px 0 3px}input,select,textarea{width:100%;box-sizing:border-box;border:1px solid #aab6c0;border-radius:5px;padding:9px;font:inherit}textarea{height:115px}button{background:#e65f17;color:#fff;border:0;border-radius:5px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer;margin:12px 8px 0 0}.secondary{background:#34495e}.stats{display:flex;gap:10px;flex-wrap:wrap}.stat{background:#edf1f4;border-radius:5px;padding:8px 12px}.stat b{font-size:20px;display:block}pre{white-space:pre-wrap;background:#17212b;color:#f7f9fb;border-radius:7px;padding:16px;line-height:1.5}.source a{color:#075985;overflow-wrap:anywhere}.hidden{display:none}@media(max-width:600px){body{padding:18px 12px}.top{align-items:start;flex-direction:column}}
</style></head><body><header class=\"top\"><div><h1>News Summarizer</h1><div class=\"muted\">Source-attributed scripts for YouTube Shorts</div></div><div class=\"muted\">Local-first · No publishing from this app</div></header>
<div class=\"notice\"><b>Editorial standard:</b> use at least two distinct publishers where possible, retain every original link, and review claims before publishing. Multiple sources improve context; they do not prove a script is neutral.</div>
<section class=\"card\"><h2>1. Find coverage</h2><p class=\"muted\">GDELT can find different publishers automatically. Guardian article text is available when <code>GUARDIAN_API_KEY</code> is configured.</p><form method=\"post\"><input type=\"hidden\" name=\"action\" value=\"discover\"><div class=\"grid\"><div><label>Topic</label><input name=\"query\" required placeholder=\"e.g. central-bank rate decision\"></div><div><label>Section</label><select name=\"section\"><option>general</option><option>world</option><option>business</option></select></div></div><button>Find coverage automatically</button></form></section>
<section class=\"card\"><h2>2. Create a balanced, cited draft</h2><p class=\"muted\">Paste source text you are allowed to use. Source 1 supplies the headline; sources 2–3 provide comparison coverage.</p><form method=\"post\"><input type=\"hidden\" name=\"action\" value=\"draft\"><label>Topic / script headline</label><input name=\"topic\" required placeholder=\"What happened?\"><div class=\"grid\">__SOURCE_1____SOURCE_2____SOURCE_3__</div><button>Generate 60-second script</button><button type=\"reset\" class=\"secondary\">Clear draft</button></form></section>
<section><h2>Recent local scripts</h2>__HISTORY__</section>__RESULT__
<script>function copyScript(){const value=document.getElementById('script-text').innerText;navigator.clipboard.writeText(value);document.getElementById('copy-status').textContent='Copied.'}</script></body></html>"""


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
    return f'<div class="source"><b>{html.escape(article.publisher)}</b> · {words} saved words<br><a target="_blank" href="{html.escape(article.url, quote=True)}">Read original article</a></div>'


def draft_result(script: Script, articles: list[Article]) -> str:
    publishers = len({item.publisher.casefold() for item in articles})
    status = "Ready for editorial review" if publishers >= 2 else "Add another publisher for broader context"
    sources = "".join(source_card(item) for item in articles)
    markdown = html.escape(to_markdown(script))
    return f"""<section class=\"card\"><h2>3. Review your draft</h2><div class=\"stats\"><div class=\"stat\"><b>{len(articles)}</b>sources</div><div class=\"stat\"><b>{publishers}</b>publishers</div><div class=\"stat\"><b>~{len(script.body.split()) // 2}</b>seconds</div><div class=\"stat\"><b>{html.escape(status)}</b></div></div><h3>Narration</h3><pre id=\"script-text\">{html.escape(script.body)}</pre><button type=\"button\" onclick=\"copyScript()\">Copy script</button><span id=\"copy-status\" class=\"muted\"></span><h3>Source links for description</h3>{sources}<details><summary>View Markdown export</summary><pre>{markdown}</pre></details></section>"""


def render(store: Store, result: str = "") -> str:
    history = store.recent_scripts()
    if history:
        items = "".join(f'<div class="source"><b>{html.escape(item.title)}</b><br><small>{html.escape(item.created_at)}</small><br><a href="{html.escape(item.article_url, quote=True)}" target="_blank">Primary original source</a></div>' for item in history)
    else:
        items = '<p class="muted">No scripts saved yet.</p>'
    return PAGE.replace("__SOURCE_1__", source_fields(1, True)).replace("__SOURCE_2__", source_fields(2)).replace("__SOURCE_3__", source_fields(3)).replace("__HISTORY__", items).replace("__RESULT__", result)


def serve(data_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    store = Store(data_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send(render(store))

        def do_POST(self) -> None:  # noqa: N802
            fields = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            try:
                if fields.get("action", [""])[0] == "discover":
                    topic = fields["query"][0].strip()
                    licensed, comparisons = discover(topic, fields.get("section", ["general"])[0])
                    for article in [*licensed, *comparisons]:
                        store.save_article(article)
                    cards = "".join(source_card(article) for article in [*licensed, *comparisons])
                    result = f'<section class="card"><h2>Coverage found</h2>{cards}<p class="muted">Use the source editor above to compare text and generate a cited narration.</p></section>' if cards else '<section class="card">No coverage returned. Try a more specific topic later.</section>'
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
