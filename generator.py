"""內容農場文章產生器。

有 GEMINI_API_KEY 就呼叫 Google Gemini（免費額度）；沒有就用內建模板離線亂湊。
金鑰到 https://aistudio.google.com/apikey 免費申請。

    python generator.py -n 5            # 產 5 篇
    python generator.py -n 3 -k 喝水     # 指定關鍵字
    python generator.py -n 10 --offline # 強制離線模板，不花錢
"""

import argparse
import os
import random
import time

from pydantic import BaseModel

import db

KEYWORDS = [
    "喝水", "睡覺", "咖啡", "手機", "走路", "存錢", "早餐", "洗澡", "貓", "冷氣",
    "泡麵", "爬樓梯", "滑手機", "加班", "吃香蕉", "深呼吸", "曬太陽", "打哈欠",
]

PERSONAS = [
    "極度酸民的鄉民",
    "中二病末期的少年",
    "愛轉貼長輩圖的阿姨",
    "自稱前 Google 工程師的成功學講師",
    "過度熱情的直銷上線",
]

MODEL = os.environ.get("FARM_MODEL", "gemini-3.8-flash")


class Article(BaseModel):
    title: str
    content: str


def build_prompt(keyword, persona):
    return (
        f"你是一個「諷刺性質」內容農場的資深編輯，人設是：{persona}。\n"
        f"請針對『{keyword}』寫一篇約 500 字的繁體中文文章，用來娛樂讀者、諷刺農場文。\n"
        "規則：\n"
        "1. 標題要用「震驚體」，例如「99%的人都不知道」、「看完沉默了」、「這招太神了」。\n"
        "2. 第一段用廢話開場，不斷重複關鍵字但沒有實質內容。\n"
        "3. 中間列出 3 點看似專業但其實是常識的建議（不要給出危險或錯誤的健康、金融建議）。\n"
        "4. 結尾呼籲讀者分享給親朋好友。\n"
        "5. 全程維持人設語氣，越浮誇越好。\n"
        "content 用純文字，段落之間空一行。"
    )


def generate_with_gemini(keyword, persona):
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    interaction = client.interactions.create(
        model=MODEL,
        input=build_prompt(keyword, persona),
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": Article.model_json_schema(),
        },
    )
    return Article.model_validate_json(interaction.output_text)


# ---------- 離線模板：不用 API，純靠排列組合 ----------

TITLE_TEMPLATES = [
    "99%的人都不知道！{k}原來還有這種隱藏用法，看完沉默了",
    "醫生朋友偷偷告訴我：每天{k}的人，後來都怎麼了？",
    "{k}這件事，日本人做了 30 年，台灣人卻現在才知道…",
    "震驚！{k}竟然跟你的人生息息相關，第3點太神了",
    "別再錯誤{k}了！專家：這樣做才是對的（快轉給家人）",
]

OPENINGS = [
    "說到{k}，相信大家都不陌生。{k}是我們生活中常見的{k}，但你真的了解{k}嗎？其實{k}這件事，就跟{k}一樣，非常重要。",
    "{k}，{k}，又是{k}。每天都有無數的人在{k}，但很少有人停下來想一想：{k}到底是什麼？今天小編就要帶大家深入了解{k}。",
]

TIPS = [
    "適量就好：任何事情過量都不好，{k}也是。",
    "保持規律：每天固定時間{k}，身體會記住你的努力。",
    "量力而為：如果{k}讓你不舒服，就先停下來休息。",
    "多問專業：關於{k}的疑問，請諮詢專業人士。",
    "持之以恆：{k}不是一天兩天的事，而是一輩子的事。",
    "用心感受：{k}的時候放下手機，專注在當下。",
]

ENDINGS = [
    "看完是不是覺得{k}一點都不簡單呢？趕快分享給你最愛的家人朋友，讓更多人知道{k}的秘密！",
    "如果你覺得這篇文章對你有幫助，請按讚分享！不轉不是台灣人！",
]

PERSONA_FLAVOR = {
    "極度酸民的鄉民": "（是說這種常識也要寫一篇，笑死）",
    "中二病末期的少年": "（吾之右手已感應到{k}的封印正在解開…）",
    "愛轉貼長輩圖的阿姨": "（早安🌸平安喜樂🌸記得{k}喔🙏）",
    "自稱前 Google 工程師的成功學講師": "（我在矽谷的時候，大家都這樣{k}。）",
    "過度熱情的直銷上線": "（想知道更多{k}的財富密碼嗎？私訊我！）",
}


def generate_offline(keyword, persona):
    k = keyword
    tips = random.sample(TIPS, 3)
    paragraphs = [
        random.choice(OPENINGS).format(k=k),
        PERSONA_FLAVOR[persona].format(k=k),
        "以下整理出 3 個關於{k}的關鍵重點：".format(k=k),
        *[f"{i}. {t.format(k=k)}" for i, t in enumerate(tips, 1)],
        random.choice(ENDINGS).format(k=k),
    ]
    return Article(title=random.choice(TITLE_TEMPLATES).format(k=k), content="\n\n".join(paragraphs))


def has_credentials():
    return bool(os.environ.get("GEMINI_API_KEY"))


def generate_one(keyword=None, offline=False, retries=2):
    keyword = keyword or random.choice(KEYWORDS)
    persona = random.choice(PERSONAS)

    if not offline and has_credentials():
        for attempt in range(retries + 1):
            try:
                art = generate_with_gemini(keyword, persona)
                return db.add_article(keyword, persona, art.title, art.content, MODEL)
            except Exception as e:  # 免費額度常撞 429，退避後重試
                print(f"  Gemini 失敗（第 {attempt + 1} 次）：{e}")
                time.sleep(20 * (attempt + 1))
        print("  改用離線模板")

    art = generate_offline(keyword, persona)
    return db.add_article(keyword, persona, art.title, art.content, "offline-template")


def main():
    parser = argparse.ArgumentParser(description="內容農場文章產生器")
    parser.add_argument("-n", type=int, default=5, help="產生幾篇（上限 50，避免帳單爆炸）")
    parser.add_argument("-k", "--keyword", help="指定關鍵字，不給就隨機")
    parser.add_argument("--sleep", type=float, default=8.0, help="每篇之間間隔秒數（免費額度有每分鐘上限）")
    parser.add_argument("--offline", action="store_true", help="不呼叫 API，只用模板")
    args = parser.parse_args()

    db.init_db()
    n = max(1, min(args.n, 50))
    for i in range(n):
        article_id = generate_one(args.keyword, args.offline)
        print(f"[{i + 1}/{n}] 已產生文章 #{article_id}")
        if i < n - 1:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
