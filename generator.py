"""內容農場文章產生器。

有設任何一家免費 API 的金鑰（見 PROVIDERS）就輪流呼叫；都沒有就用內建模板離線亂湊。

    python generator.py -n 5            # 產 5 篇
    python generator.py -n 3 -k 喝水     # 指定關鍵字
    python generator.py -n 10 --offline # 強制離線模板，不花錢
    python generator.py -n 3 --news     # 抓 Google 新聞頭條當題材
"""

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request

from pydantic import BaseModel

import db
import news

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

# 各家免費 API。除了 Gemini，其他都是 OpenAI 相容格式（POST {base}/chat/completions）。
# 沒設金鑰的那家會自動略過，所以只申請其中幾家也能跑。
PROVIDERS = {
    "gemini": {"env": "GEMINI_API_KEY"},  # https://aistudio.google.com/apikey
    "groq": {"env": "GROQ_API_KEY", "base": "https://api.groq.com/openai/v1"},  # https://console.groq.com/keys
    "mistral": {"env": "MISTRAL_API_KEY", "base": "https://api.mistral.ai/v1"},  # https://console.mistral.ai/api-keys
    "zhipu": {"env": "ZHIPU_API_KEY", "base": "https://open.bigmodel.cn/api/paas/v4"},  # https://open.bigmodel.cn
    "openrouter": {"env": "OPENROUTER_API_KEY", "base": "https://openrouter.ai/api/v1"},  # https://openrouter.ai/keys
    # Actions 內建的 GITHUB_TOKEN 就能用（workflow 要給 models: read 權限），不用另外申請
    "github": {"env": "GITHUB_TOKEN", "base": "https://models.github.ai/inference"},
}

# 免費額度大多是「每個模型分開算」（例如 gemini-3.8-flash 一天只有 20 次），
# 所以照順序輪流用，用完一個換下一個。可用 FARM_MODELS="供應商:模型,..." 覆寫（沒寫供應商 = gemini）。
DEFAULT_MODELS = [
    "gemini:gemini-3.8-flash", "gemini:gemini-3.7-flash", "gemini:gemini-3.6-flash",
    "groq:openai/gpt-oss-120b", "groq:llama-3.3-70b-versatile",
    "mistral:mistral-large-latest", "zhipu:glm-4.7-flash", "github:openai/gpt-4.1",
    "gemini:gemini-3.5-flash", "gemini:gemini-2.5-flash",
    "mistral:mistral-small-latest", "zhipu:glm-4-flash", "github:openai/gpt-4.1-mini",
    "openrouter:meta-llama/llama-3.3-70b-instruct:free",
    "gemini:gemini-3.5-flash-lite", "gemini:gemini-3.1-flash-lite", "gemini:gemini-2.5-flash-lite",
]
MODELS = [
    m if m.split(":", 1)[0] in PROVIDERS else f"gemini:{m}"
    for m in (m.strip() for m in os.environ.get("FARM_MODELS", ",".join(DEFAULT_MODELS)).split(","))
    if m
]
exhausted = set()  # 這次執行中已經用完額度（或不能用）的模型


class Article(BaseModel):
    title: str
    content: str


def build_prompt(keyword, persona):
    return (
        f"你是一個「諷刺性質」內容農場的資深編輯，人設是：{persona}。\n"
        f"請針對『{keyword}』寫一篇約 1200 字的繁體中文文章，用來娛樂讀者、諷刺農場文。\n"
        "結構（每部分都要寫足，不要草草帶過）：\n"
        "1. 標題要用「震驚體」，例如「99%的人都不知道」、「看完沉默了」、「這招太神了」。\n"
        "2. 開場兩三段廢話，不斷重複關鍵字但沒有實質內容。\n"
        "3. 小編自己跟這個主題的「親身經歷」，越離題越好。\n"
        "4. 列出 5 點看似專業但其實是常識的建議，每點都要硬掰一小段解釋"
        "（不要給出危險或錯誤的健康、金融建議）。\n"
        "5. 「網友熱議」：虛構幾則網友留言互相抬槓（用網友A、網友B，不要用真實人名）。\n"
        "6. 結尾呼籲讀者分享給親朋好友。\n"
        "全程維持人設語氣，越浮誇越好。content 用純文字，段落之間空一行。"
    )


GOSSIP_STYLE = (
    "這是娛樂八卦新聞，請用「茶水間爆料」的口吻寫，像在跟姊妹淘／兄弟講八卦："
    "「欸你有看到嗎」、「我跟你說喔」、「懂的都懂」。"
    "但八卦只能八卦標題本身，不可以腦補當事人的感情、私生活、外貌身材或任何標題沒提到的事。\n"
)


def build_news_prompt(headline, persona):
    gossip = GOSSIP_STYLE if headline.get("category") == "娛樂" else ""
    return (
        f"你是一個「諷刺性質」內容農場的資深編輯，人設是：{persona}。\n"
        f"今天的新聞標題是：『{headline['title']}』（來源：{headline['source']}）。\n"
        "請用這個人設寫一篇約 1200 字的繁體中文「評論吐槽文」，用來娛樂讀者、諷刺農場文。\n"
        + gossip
        + "規則：\n"
        "1. 標題要用「震驚體」，例如「看完沉默了」、「網友吵翻」、「真相讓人傻眼」。\n"
        "2. 你只知道新聞標題，所以只能針對標題本身發表感想與吐槽，"
        "絕對不可以捏造標題裡沒有的事實、數字、人名、引言或後續發展。"
        "篇幅要靠小編的感想、離題聯想和浮誇語氣撐起來，不是靠編造新聞內容。\n"
        "3. 寫成個人評論，不要寫得像新聞報導；不要嘲諷災難、意外、犯罪或疾病的受害者。\n"
        "4. 結構（每部分都要寫足）：廢話開場兩三段 → 小編看到標題的心路歷程 → "
        "小編的「專業分析」3～5 點（其實都是廢話） → 「網友可能會吵什麼」：虛構網友A、網友B"
        "互相抬槓（只吵對標題的看法，不可以替真實人物發言） → 結尾。\n"
        "5. 結尾提醒讀者去看原始新聞，並呼籲分享。\n"
        "6. 全程維持人設語氣，越浮誇越好。\n"
        "content 用純文字，段落之間空一行。"
    )


def call_gemini(model, prompt):
    from google import genai

    # 設逾時（毫秒），不然 Gemini 卡住時會一直等到 Actions 的 30 分鐘上限
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options={"timeout": 120_000},
    )
    interaction = client.interactions.create(
        model=model,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": Article.model_json_schema(),
        },
    )
    return Article.model_validate_json(interaction.output_text)


JSON_HINT = '\n\n只輸出一個 JSON 物件，不要任何其他文字：{"title": "標題", "content": "內文"}'


def call_openai_compat(provider, model, prompt):
    p = PROVIDERS[provider]
    req = urllib.request.Request(
        f"{p['base']}/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt + JSON_HINT}],
            "response_format": {"type": "json_object"},
        }).encode(),
        headers={"Authorization": f"Bearer {os.environ[p['env']]}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:  # 把錯誤內容帶出來，才看得出是額度用完還是模型名稱錯
        raise RuntimeError(f"{e.code} {e.read().decode(errors='replace')}") from None
    text = data["choices"][0]["message"]["content"].strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```")  # 有些模型會包 code block
    return Article.model_validate_json(text)


def call_model(entry, prompt):
    provider, model = entry.split(":", 1)
    if provider == "gemini":
        return call_gemini(model, prompt)
    return call_openai_compat(provider, model, prompt)


def available_models():
    """有設金鑰的那幾家的模型。"""
    return [m for m in MODELS if os.environ.get(PROVIDERS[m.split(":", 1)[0]]["env"])]


def generate_with_gemini(prompt):
    """輪流試各家免費模型，回傳 (模型名稱, 文章)；全部都不行就回傳 None。"""
    for model in available_models():
        if model in exhausted:
            continue
        for attempt in range(2):
            try:
                return model, call_model(model, prompt)
            except Exception as e:
                msg = str(e)
                print(f"  {model} 失敗：{msg[:160]}")
                if "429" in msg and "per day" not in msg and attempt == 0:
                    time.sleep(60)  # 每分鐘上限：等一分鐘再試同一個模型
                    continue
                if "503" not in msg:  # 503 只是暫時忙線，下一篇還可以再試這個模型
                    exhausted.add(model)  # 今天額度用完或這個模型不能用
                break  # 這篇先換下一個模型
    return None


# ---------- 離線模板：不用 API，純靠排列組合 ----------

TITLE_TEMPLATES = [
    "99%的人都不知道！{k}原來還有這種隱藏用法，看完沉默了",
    "醫生朋友偷偷告訴我：每天{k}的人，後來都怎麼了？",
    "{k}這件事，日本人做了 30 年，台灣人卻現在才知道…",
    "震驚！{k}竟然跟你的人生息息相關，第3點太神了",
    "別再錯誤{k}了！專家：這樣做才是對的（快轉給家人）",
]

NEWS_TITLE_TEMPLATES = [
    "看到「{t}」，小編沉默了…",
    "「{t}」網友吵翻！看完我只想說一句話",
    "震驚！「{t}」這則新聞，99%的人都只看標題",
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

NEWS_TIPS = [
    "先看完全文：只看標題就留言，是農場最喜歡的讀者。",
    "多看幾家媒體：同一件事，換個標題就像換了一個世界。",
    "冷靜再分享：轉貼之前，先確認不是去年的舊聞。",
    "注意來源：截圖不是新聞，長輩群組也不是通訊社。",
]

ENDINGS = [
    "看完是不是覺得{k}一點都不簡單呢？趕快分享給你最愛的家人朋友，讓更多人知道{k}的秘密！",
    "如果你覺得這篇文章對你有幫助，請按讚分享！不轉不是台灣人！",
]

PERSONA_FLAVOR = {
    "極度酸民的鄉民": "（是說這種東西也要寫一篇，笑死）",
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
        f"以下整理出 3 個關於{k}的關鍵重點：",
        *[f"{i}. {t.format(k=k)}" for i, t in enumerate(tips, 1)],
        random.choice(ENDINGS).format(k=k),
    ]
    return Article(title=random.choice(TITLE_TEMPLATES).format(k=k), content="\n\n".join(paragraphs))


def generate_offline_news(headline, persona):
    t = headline["title"]
    tips = random.sample(NEWS_TIPS, 3)
    paragraphs = [
        f"今天的新聞「{t}」，相信大家都看到了。這則新聞，真的是一則新聞。小編看完標題之後，久久不能自已，只能說：這就是新聞啊！",
        PERSONA_FLAVOR[persona].format(k="看新聞"),
        "身為專業的農場編輯，小編整理出 3 個看新聞的重點：",
        *[f"{i}. {tip}" for i, tip in enumerate(tips, 1)],
        "想知道完整內容，請點上方的原始新聞連結。覺得小編說得有道理，就分享給親朋好友吧！",
    ]
    return Article(title=random.choice(NEWS_TITLE_TEMPLATES).format(t=t), content="\n\n".join(paragraphs))


def has_credentials():
    return bool(available_models())


def generate_one(keyword=None, offline=False, headline=None):
    """headline 是 news.fetch_headlines() 的一筆；有給就寫時事評論，沒給就用關鍵字。

    有金鑰時 Gemini 失敗就回傳 None（跳過，不寫模板廢文，新聞下次還能再寫）。
    """
    persona = random.choice(PERSONAS)
    if headline:
        keyword = headline["category"]
        prompt = build_news_prompt(headline, persona)
        news_fields = {"news_title": headline["title"], "news_url": headline["url"]}
    else:
        keyword = keyword or random.choice(KEYWORDS)
        prompt = build_prompt(keyword, persona)
        news_fields = {}

    if not offline and has_credentials():
        result = generate_with_gemini(prompt)
        if result is None:
            return None
        model, art = result
        return db.add_article(keyword, persona, art.title, art.content, model, **news_fields)

    art = generate_offline_news(headline, persona) if headline else generate_offline(keyword, persona)
    return db.add_article(keyword, persona, art.title, art.content, "offline-template", **news_fields)


def main():
    parser = argparse.ArgumentParser(description="內容農場文章產生器")
    parser.add_argument("-n", type=int, default=5, help="產生幾篇（上限 50，避免帳單爆炸）")
    parser.add_argument("-k", "--keyword", help="指定關鍵字，不給就隨機")
    parser.add_argument("--sleep", type=float, default=8.0, help="每篇之間間隔秒數（免費額度有每分鐘上限）")
    parser.add_argument("--offline", action="store_true", help="不呼叫 API，只用模板")
    parser.add_argument("--news", action="store_true", help="用 Google 新聞頭條當題材（跳過寫過的）")
    args = parser.parse_args()

    db.init_db()
    n = max(1, min(args.n, 50))

    headlines = []
    if args.news:
        seen = db.used_news_urls()
        headlines = [h for h in news.fetch_headlines() if h["url"] not in seen][:n]
        if not headlines:
            print("沒有新的新聞可以寫")
            return
        n = len(headlines)

    for i in range(n):
        article_id = generate_one(args.keyword, args.offline, headlines[i] if headlines else None)
        if article_id is None:
            print(f"[{i + 1}/{n}] 跳過")
            if len(exhausted) == len(available_models()):
                print("所有免費模型今天的額度都用完了，先停")
                break
        else:
            print(f"[{i + 1}/{n}] 已產生文章 #{article_id}")
        if i < n - 1:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
