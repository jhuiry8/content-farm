"""抓 Google 新聞台灣版的即時頭條（免費 RSS，不用 API key）。"""

import urllib.request
import xml.etree.ElementTree as ET
from itertools import zip_longest

PARAMS = "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
FEEDS = {
    "娛樂": f"https://news.google.com/rss/headlines/section/topic/ENTERTAINMENT?{PARAMS}",
    "焦點": f"https://news.google.com/rss?{PARAMS}",
    "台灣": f"https://news.google.com/rss/headlines/section/topic/NATION?{PARAMS}",
    "國際": f"https://news.google.com/rss/headlines/section/topic/WORLD?{PARAMS}",
    "財經": f"https://news.google.com/rss/headlines/section/topic/BUSINESS?{PARAMS}",
    "科技": f"https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?{PARAMS}",
    "體育": f"https://news.google.com/rss/headlines/section/topic/SPORTS?{PARAMS}",
    "科學": f"https://news.google.com/rss/headlines/section/topic/SCIENCE?{PARAMS}",
    "健康": f"https://news.google.com/rss/headlines/section/topic/HEALTH?{PARAMS}",
}
# 每輪從該分類拿幾則，沒列的拿 1 則（八卦比較有農場味，多拿一點）
WEIGHTS = {"娛樂": 2}


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
    """所有分類的頭條，各分類輪流排（娛樂第1、2則、焦點第1則…娛樂第3、4則…），網址重複的只留一則。"""
    feeds = []
    for category, url in FEEDS.items():
        try:
            items = fetch_feed(category, url)
        except Exception as e:
            print(f"  抓不到 {category} 新聞：{e}")
            continue
        w = WEIGHTS.get(category, 1)
        feeds.append([items[i : i + w] for i in range(0, len(items), w)])

    seen, result = set(), []
    for row in zip_longest(*feeds, fillvalue=[]):
        for h in (h for chunk in row for h in chunk):
            if h["url"] not in seen:
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
