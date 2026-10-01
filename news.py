"""抓 Google 新聞台灣版的即時頭條（免費 RSS，不用 API key）。"""

import urllib.request
import xml.etree.ElementTree as ET
from itertools import zip_longest

PARAMS = "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
FEEDS = {
    "焦點": f"https://news.google.com/rss?{PARAMS}",
    "台灣": f"https://news.google.com/rss/headlines/section/topic/NATION?{PARAMS}",
    "國際": f"https://news.google.com/rss/headlines/section/topic/WORLD?{PARAMS}",
    "財經": f"https://news.google.com/rss/headlines/section/topic/BUSINESS?{PARAMS}",
    "科技": f"https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?{PARAMS}",
    "娛樂": f"https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?{PARAMS}",
    "體育": f"https://news.google.com/rss/headlines/section/topic/SPORTS?{PARAMS}",
    "科學": f"https://news.google.com/rss/headlines/section/topic/SCIENCE?{PARAMS}",
    "健康": f"https://news.google.com/rss/headlines/section/topic/HEALTH?{PARAMS}",
}


def fetch_feed(category, url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        root = ET.fromstring(resp.read())

    headlines = []
    for item in root.iter("item"):
        source = item.findtext("source") or ""
        title = item.findtext("title") or ""
        # Google 新聞標題結尾會帶「 - 媒體名」，拿掉
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")]
        headlines.append({"title": title.strip(), "source": source, "url": item.findtext("link"), "category": category})
    return headlines


def fetch_headlines():
    """所有分類的頭條，各分類輪流排（焦點第1則、台灣第1則…焦點第2則…），網址重複的只留一則。"""
    feeds = []
    for category, url in FEEDS.items():
        try:
            feeds.append(fetch_feed(category, url))
        except Exception as e:
            print(f"  抓不到 {category} 新聞：{e}")

    seen, result = set(), []
    for row in zip_longest(*feeds):
        for h in row:
            if h and h["url"] not in seen:
                seen.add(h["url"])
                result.append(h)
    return result


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    headlines = fetch_headlines()
    print(f"共 {len(headlines)} 則")
    for h in headlines[:20]:
        print(f"[{h['category']}][{h['source']}] {h['title']}")
