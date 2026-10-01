"""抓 Google 新聞台灣版的即時頭條（免費 RSS，不用 API key）。"""

import urllib.request
import xml.etree.ElementTree as ET

FEED = "https://news.google.com/rss?hl=zh-TW&gl=TW&ceid=TW:zh-Hant"


def fetch_headlines(limit=30):
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())

    headlines = []
    for item in root.iter("item"):
        source = item.findtext("source") or ""
        title = item.findtext("title") or ""
        # Google 新聞標題結尾會帶「 - 媒體名」，拿掉
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")]
        headlines.append({"title": title.strip(), "source": source, "url": item.findtext("link")})
        if len(headlines) >= limit:
            break
    return headlines


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    for h in fetch_headlines(10):
        print(f"[{h['source']}] {h['title']}")
