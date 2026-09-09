from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, abort

from config import CATEGORY_ARTICLE_LIMIT, CATEGORY_LABELS
from services.feeds import get_articles
from services.script_generator import generate_script

app = Flask(__name__)


@app.context_processor
def inject_categories():
    return {"categories": CATEGORY_LABELS}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/category/<category>")
def category(category):
    if category not in CATEGORY_LABELS:
        abort(404)

    error = None
    articles = []
    try:
        articles = get_articles(category, limit=CATEGORY_ARTICLE_LIMIT)
    except (ValueError, RuntimeError) as exc:
        error = str(exc)

    for art in articles:
        try:
            art["script"] = generate_script(art)
            art["script_error"] = None
        except RuntimeError as exc:
            art["script"] = None
            art["script_error"] = str(exc)

    return render_template(
        "category.html",
        category=category,
        label=CATEGORY_LABELS[category],
        articles=articles,
        error=error,
    )


@app.errorhandler(404)
def not_found(_exc):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
