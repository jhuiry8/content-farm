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


def add_article(keyword, persona, title, content, source):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO articles (keyword, persona, title, content, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (keyword, persona, title, content, source, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


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
