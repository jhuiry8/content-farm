"""把 Flask 網站匯出成純靜態 HTML（放到 site/），給 GitHub Pages 這類免費靜態託管用。

    python build.py                         # 網站放在網域根目錄
    BASE_PATH=/repo-name python build.py    # GitHub Pages 專案網站（網址有 /repo-name/）
"""

import os
import shutil
from pathlib import Path
from urllib.parse import unquote

import db
from app import app

OUT = Path(__file__).with_name("site")
BASE_PATH = os.environ.get("BASE_PATH", "").rstrip("/")


def save(client, url):
    # base_url 帶 BASE_PATH，url_for 產生的連結才會有前綴
    resp = client.get(url, base_url=f"http://localhost{BASE_PATH}/")
    if resp.status_code != 200:
        raise RuntimeError(f"{url} -> {resp.status_code}")
    target = OUT / unquote(url).lstrip("/") / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(resp.data)


def main():
    app.config["STATIC_SITE"] = True
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(Path(__file__).with_name("static"), OUT / "static")

    client = app.test_client()

    with app.test_request_context():
        from flask import url_for

        urls = ["/"]
        urls += [url_for("tag", keyword=t["keyword"]) for t in db.keywords()]
        urls += [url_for("article", article_id=a["id"]) for a in db.list_articles(limit=10**9)]

    for url in urls:
        save(client, url)
    (OUT / ".nojekyll").touch()
    print(f"匯出 {len(urls)} 頁到 {OUT}")


if __name__ == "__main__":
    main()
