from newssummarizer.models import Article
from newssummarizer.script import make_script
from newssummarizer.store import Store


def test_saved_article_generates_a_script_offline(tmp_path):
    article = Article(
        url="https://www.reuters.com/world/example/",
        title="Example story",
        section="world",
        publisher="Reuters",
        text=("First factual sentence contains enough detail to be retained. "
              "Second factual sentence also has enough words for a short script."),
    )
    store = Store(tmp_path)
    store.save_article(article)
    script = make_script(store.all_articles("world")[0], [])
    path = store.save_script(script)
    assert article.url in path.read_text()
    assert "Reuters reports" in script.body
