# NewSummarizer

A small Flask app that turns Reuters news articles into ~60-second scripts for YouTube Shorts.

- Browse articles by category (World, Business, Technology, Markets, Sports), pulled from Reuters' public RSS feeds.
- Open an article to generate a spoken-style script (~150-160 words, roughly 60 seconds) using Claude.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
.venv/bin/flask --app app run
```

Then open http://127.0.0.1:5000.

## Notes

- Reuters does not offer a scraping-friendly API; this app relies on their public RSS
  feeds (configured in `config.py`). If a feed URL stops working, update it there —
  Reuters has changed its feed hosting over time.
- Script generation requires an `ANTHROPIC_API_KEY` (see `.env.example`). Without one,
  article pages still load but show an error instead of a script.
