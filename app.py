from flask import Flask, abort, redirect, render_template, request, url_for

import db
import generator

app = Flask(__name__)
app.config["STATIC_SITE"] = False  # build.py 匯出靜態網站時設成 True：不顯示產文表單、不計瀏覽數
db.init_db()


@app.context_processor
def sidebar():
    return {"hot": db.hot_articles(), "tags": db.keywords(), "static_site": app.config["STATIC_SITE"]}


@app.route("/")
def index():
    return render_template("index.html", articles=db.list_articles(), heading="最新爆料")


@app.route("/tag/<keyword>/")
def tag(keyword):
    return render_template("index.html", articles=db.list_articles(keyword=keyword), heading=f"#{keyword}")


@app.route("/article/<int:article_id>/")
def article(article_id):
    art = db.get_article(article_id, count_view=not app.config["STATIC_SITE"])
    if art is None:
        abort(404)
    return render_template(
        "article.html", a=art, paragraphs=art["content"].split("\n\n"), comments=db.list_comments(article_id)
    )


@app.route("/generate", methods=["POST"])
def generate():
    # 只允許本機觸發，避免網站公開後被路人狂按燒 API 額度
    if request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)
    article_id = generator.generate_one(request.form.get("keyword") or None)
    return redirect(url_for("article", article_id=article_id))


if __name__ == "__main__":
    app.run(debug=True)
