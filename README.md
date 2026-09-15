# NewSummarizer

An offline-first personal research tool for turning source material into compact, detailed video explainers. Every generated script retains original source links and labels comparison coverage honestly rather than promising neutrality.

## What works offline

`generate` reads only local cached articles and writes scripts locally. It does **not** fetch the web or use a cloud language model. Run `sync` while online to refresh the local cache *only where Reuters permits the request*. The optional `--with-perspectives` switch is online-only because it discovers new coverage using GDELT.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
# Online: cache current public stories from a Reuters section
newssummarizer sync world --limit 10
newssummarizer sync business --limit 10

# If Reuters blocks programmatic retrieval, import a text file you lawfully saved.
# This preserves the original article link in the resulting script.
newssummarizer import world saved-reuters-story.txt \
  --url https://www.reuters.com/world/example/ --title "Story headline"

# Offline: write JSON scripts using only cached content
newssummarizer generate world

# Online: include up to three other outlets' original links per story
newssummarizer generate business --with-perspectives

# Open a local browser interface (http://127.0.0.1:8765)
newssummarizer serve

# Online: find cross-publisher coverage through GDELT (no key required)
newssummarizer discover "central bank interest rate decision"
```

Scripts are saved to `data/scripts/` as JSON and Markdown. The Markdown version is ready to paste into a production document and includes the original links.

## Connectors

| Connector | Setup | Use |
| --- | --- | --- |
| GDELT DOC 2.0 | No key | Finds cross-publisher coverage and original links. |
| Guardian Open Platform | Set `GUARDIAN_API_KEY` in your terminal | Retrieves permissioned Guardian article text for automated narration. |
| TheNewsAPI | Set `THENEWSAPI_API_TOKEN` in your terminal | Supplies attributed multi-publisher descriptions for automated narration. |
| Saved text | No key | Best offline mode: script from material you already have permission to use. |

To enable Guardian before launching the local browser interface:

```bash
export GUARDIAN_API_KEY="your-developer-key"
# Optional: adds attributed descriptions from additional publishers
export THENEWSAPI_API_TOKEN="your-api-token"
newssummarizer serve
```

Keys belong in your local shell or a secret manager—never in the browser UI or Git. The app does not collect, store, or transmit a key.

In the browser, choose a category under **Generate a category briefing**, select how many scripts to make, then choose **Generate category scripts**. The app creates one local, cited script per distinct article returned in that category. It will not invent a script when configured APIs return no usable article text. Use **Run test preview** at any time to see three fictional, offline-only examples of the final script layout.

## Limits and responsible use

This is a research aid, not a fact-checker. A second outlet is comparison coverage, not proof of neutrality or accuracy. Read the linked original reporting, compare publication dates and source ownership, and verify disputed claims. The tool accesses only publicly available pages and approved APIs; it does not bypass paywalls, authentication, robots controls, or site restrictions. In testing, Reuters served the website interactively but returned a 401 to ordinary Python retrieval; the tool therefore stops and explains how to use an approved feed/API or local, lawfully saved text. Review Reuters' and each publisher's terms before collecting material at scale.
