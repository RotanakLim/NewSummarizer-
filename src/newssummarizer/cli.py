from __future__ import annotations

import argparse
from pathlib import Path

from .compare import corroborating_articles
from .fetch import SourceAccessError, fetch_article, import_article, reuters_section_urls
from .script import make_script
from .store import Store
from .web import serve
from .providers import ProviderUnavailable, discover


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache Reuters stories and generate offline scripts.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="ONLINE: cache public Reuters section stories")
    sync.add_argument("section", choices=["world", "business"])
    sync.add_argument("--limit", type=int, default=10)
    imported = commands.add_parser("import", help="OFFLINE: add a lawfully saved article text file")
    imported.add_argument("section", choices=["world", "business"])
    imported.add_argument("file", type=str)
    imported.add_argument("--url", required=True, help="Original article URL to retain in the script")
    imported.add_argument("--title", required=True)
    imported.add_argument("--publisher", default="Reuters")
    generate = commands.add_parser("generate", help="OFFLINE: create scripts from cached stories")
    generate.add_argument("section", choices=["world", "business"])
    generate.add_argument("--with-perspectives", action="store_true", help="ONLINE: add fresh GDELT source links")
    web = commands.add_parser("serve", help="Run the local browser interface")
    web.add_argument("--port", type=int, default=8765)
    discover_cmd = commands.add_parser("discover", help="ONLINE: find cross-publisher coverage with GDELT")
    discover_cmd.add_argument("query")
    discover_cmd.add_argument("--section", default="general")
    args = parser.parse_args()
    store = Store(args.data_dir)
    if args.command == "serve":
        serve(args.data_dir, port=args.port)
        return
    if args.command == "discover":
        try:
            licensed, comparisons = discover(args.query, args.section)
        except ProviderUnavailable as error:
            parser.error(str(error))
        for article in licensed + comparisons:
            store.save_article(article)
            print(f"cached: {article.publisher} — {article.title} — {article.url}")
        return
    if args.command == "import":
        article = import_article(args.file, args.url, args.title, args.section, args.publisher)
        store.save_article(article)
        print(f"cached: {article.title}")
        return
    if args.command == "sync":
        try:
            for url in reuters_section_urls(args.section, args.limit):
                article = fetch_article(url, args.section)
                store.save_article(article)
                print(f"cached: {article.title}")
        except SourceAccessError as error:
            parser.error(str(error))
        return
    for article in store.all_articles(args.section):
        perspectives = corroborating_articles(article) if args.with_perspectives else []
        path = store.save_script(make_script(article, perspectives))
        print(f"wrote: {path}")
