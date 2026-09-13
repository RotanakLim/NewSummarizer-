from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .models import Article
from .providers import ProviderUnavailable, discover
from .script import make_script
from .store import Store

PAGE = """<!doctype html><html><head><meta charset=\"utf-8\"><title>News Summarizer</title><style>body{max-width:860px;margin:36px auto;font:16px system-ui;color:#17212b;padding:0 20px}input,select,textarea{width:100%;box-sizing:border-box;margin:5px 0 14px;padding:10px;font:inherit}textarea{height:145px}button{background:#e65f17;color:#fff;border:0;border-radius:4px;padding:10px 15px;font-weight:700;margin-right:8px}article,.notice{border:1px solid #d6dadd;border-radius:6px;padding:18px;margin-top:24px;white-space:pre-wrap}.notice{background:#f5f8fa}small{color:#52606d}a{color:#075985}.source{border-top:1px solid #e4e8eb;padding:10px 0}</style></head><body><h1>News Summarizer</h1><p>Generate a source-attributed YouTube Short script. Your article text and scripts stay on this computer.</p><div class=\"notice\"><strong>Automatic discovery:</strong> GDELT finds cross-publisher links without a key. Set <code>GUARDIAN_API_KEY</code> before starting the app to fetch Guardian full text automatically. Comparison links are coverage to review, not proof of neutrality.</div><form method=\"post\"><label>Story or topic</label><input name=\"query\" placeholder=\"e.g. latest central-bank interest-rate decision\"><label>Section</label><select name=\"section\"><option>general</option><option>world</option><option>business</option></select><button name=\"action\" value=\"discover\">Find coverage automatically</button><hr><h2>Or generate from saved article text</h2><label>Headline</label><input name=\"title\" placeholder=\"Article headline\"><label>Original article URL</label><input name=\"url\" placeholder=\"https://...\"><label>Article text you have permission to use</label><textarea name=\"text\" placeholder=\"Paste article text here…\"></textarea><button name=\"action\" value=\"manual\">Generate 60-second script</button></form>__RESULT__</body></html>"""


def _source_card(article: Article) -> str:
    return f'<div class="source"><strong>{html.escape(article.publisher)}</strong><br><a href="{html.escape(article.url, quote=True)}" target="_blank">{html.escape(article.title)}</a></div>'


def _script_result(article: Article, comparisons: list[Article]) -> str:
    script = make_script(article, comparisons)
    sources = "".join(_source_card(Article(url=s["url"], title=s["title"], section="", publisher=s["publisher"])) for s in script.sources)
    return f"<article><h2>60-second YouTube Short script</h2><p>{html.escape(script.body)}</p><h3>Original sources to link in your description</h3>{sources}<small>Saved locally as Markdown and JSON for reuse offline.</small></article>"


def serve(data_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    store = Store(data_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send(PAGE.replace("__RESULT__", ""))

        def do_POST(self) -> None:  # noqa: N802
            fields = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            try:
                section, action = fields.get("section", ["general"])[0], fields.get("action", [""])[0]
                if action == "discover":
                    query = fields.get("query", [""])[0].strip()
                    if not query:
                        raise ValueError("Enter a story or topic before discovering coverage.")
                    licensed, comparisons = discover(query, section)
                    for item in licensed + comparisons:
                        store.save_article(item)
                    if licensed:
                        script = make_script(licensed[0], comparisons)
                        store.save_script(script)
                        result = _script_result(licensed[0], comparisons)
                    else:
                        result = "<article><h2>Cross-publisher coverage</h2>" + "".join(_source_card(a) for a in comparisons) + "<p><small>GDELT provides original links. Add GUARDIAN_API_KEY or use saved text for automatic narration.</small></p></article>"
                else:
                    article = Article(url=fields["url"][0], title=fields["title"][0], section=section, publisher="User-supplied source", text=fields["text"][0])
                    store.save_article(article)
                    store.save_script(make_script(article, []))
                    result = _script_result(article, [])
            except (KeyError, ValueError) as error:
                result = f"<article><strong>Could not complete that request:</strong> {html.escape(str(error))}</article>"
            except ProviderUnavailable as error:
                result = f"<article><strong>Automatic discovery is temporarily unavailable:</strong> {html.escape(str(error))}</article>"
            except Exception as error:
                result = f"<article><strong>Source lookup failed:</strong> {html.escape(type(error).__name__)}. Try again later or use saved text.</article>"
            self._send(PAGE.replace("__RESULT__", result))

        def _send(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    print(f"News Summarizer is running at http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
