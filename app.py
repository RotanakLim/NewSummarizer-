from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, abort

from config import CATEGORY_LABELS
from services.feeds import get_articles, get_article
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
        articles = get_articles(category)
    except (ValueError, RuntimeError) as exc:
        error = str(exc)

    return render_template(
        "category.html",
        category=category,
        label=CATEGORY_LABELS[category],
        articles=articles,
        error=error,
    )


@app.route("/article/<article_id>")
def article(article_id):
    art = get_article(article_id)
    if art is None:
        abort(404)

    script = None
    error = None
    try:
        script = generate_script(art)
    except RuntimeError as exc:
        error = str(exc)

    return render_template("article.html", article=art, script=script, error=error)


@app.errorhandler(404)
def not_found(_exc):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
