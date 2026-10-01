import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("farm.db")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword    TEXT NOT NULL,
                persona    TEXT NOT NULL,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL,
                source     TEXT NOT NULL,
                views      INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        # 舊資料庫補上新聞欄位
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(articles)")}
        for col in ("news_title", "news_url", "reviewer", "review_note"):
            if col not in cols:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL REFERENCES articles(id),
                nickname   TEXT NOT NULL,
                content    TEXT NOT NULL,
                source     TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def add_article(keyword, persona, title, content, source, news_title=None, news_url=None,
                reviewer=None, review_note=None):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO articles (keyword, persona, title, content, source, news_title, news_url, "
            "reviewer, review_note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (keyword, persona, title, content, source, news_title, news_url, reviewer, review_note,
             datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def add_comments(article_id, comments, source):
    """comments 是 [(暱稱, 留言), ...]。"""
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.executemany(
            "INSERT INTO comments (article_id, nickname, content, source, created_at) VALUES (?, ?, ?, ?, ?)",
            [(article_id, name, text, source, now) for name, text in comments],
        )


def list_comments(article_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM comments WHERE article_id = ? ORDER BY id", (article_id,)).fetchall()


def list_articles(limit=50, keyword=None):
    with connect() as conn:
        if keyword:
            return conn.execute(
                "SELECT * FROM articles WHERE keyword = ? ORDER BY id DESC LIMIT ?", (keyword, limit)
            ).fetchall()
        return conn.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def hot_articles(limit=5):
    with connect() as conn:
        return conn.execute("SELECT * FROM articles ORDER BY views DESC, id DESC LIMIT ?", (limit,)).fetchall()


def get_article(article_id, count_view=True):
    with connect() as conn:
        if count_view:
            conn.execute("UPDATE articles SET views = views + 1 WHERE id = ?", (article_id,))
        return conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()


def keywords():
    with connect() as conn:
        return conn.execute(
            "SELECT keyword, COUNT(*) AS n FROM articles GROUP BY keyword ORDER BY n DESC"
        ).fetchall()


def used_news_urls():
    with connect() as conn:
        return {r["news_url"] for r in conn.execute("SELECT news_url FROM articles WHERE news_url IS NOT NULL")}
