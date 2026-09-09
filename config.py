import os

# Reuters public RSS feeds, keyed by the category slug used in the app's URLs.
# Reuters has changed its feed hosting over the years, so these are kept in one
# place and easy to update if a URL stops working.
CATEGORY_FEEDS = {
    "world": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best",
    "business": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "technology": "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best",
    "markets": "https://www.reutersagency.com/feed/?best-topics=markets&post_type=best",
    "sports": "https://www.reutersagency.com/feed/?best-topics=sports&post_type=best",
}

CATEGORY_LABELS = {
    "world": "World",
    "business": "Business",
    "technology": "Technology",
    "markets": "Markets",
    "sports": "Sports",
}

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

# Target word count for a spoken script that runs ~60 seconds
# (roughly 150 words/minute for clear, energetic narration).
SCRIPT_TARGET_WORDS = 155
