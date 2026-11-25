import os
import re
import json
import html
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Model ishlamasa, keyingisi sinab ko'riladi. Kerak bo'lsa GEMINI_MODEL orqali o'zgartiring.
MODELS = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"] if m]

FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://venturebeat.com/category/ai/feed/",
    "https://blog.google/technology/ai/rss/",
    "https://openai.com/news/rss.xml",
]

HOURS = 36
MAX_ITEMS = 40


def http(url, data=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": "Mozilla/5.0 (ai-news-bot)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(text, limit=300):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def strip_ns(tag):
    return tag.split("}", 1)[-1]


def read_feed(url):
    root = ET.fromstring(http(url))
    items = []
    for el in root.iter():
        if strip_ns(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            name = strip_ns(c.tag)
            if name == "link":
                f["link"] = c.get("href") or (c.text or "")
            elif name in ("title", "description", "summary", "pubDate", "published", "updated"):
                f.setdefault(name, c.text or "")
        items.append({
            "title": clean(f.get("title"), 200),
            "summary": clean(f.get("description") or f.get("summary")),
            "link": (f.get("link") or "").strip(),
            "date": parse_date(f.get("pubDate") or f.get("published") or f.get("updated")),
            "source": re.sub(r"^www\.", "", url.split("/")[2]),
        })
    return items


def collect():
    since = datetime.now(timezone.utc) - timedelta(hours=HOURS)
    all_items = []
    for url in FEEDS:
        try:
            for it in read_feed(url):
                if it["date"] is None or it["date"] >= since:
                    all_items.append(it)
        except Exception as e:
            print(f"Lenta o'qilmadi: {url} -> {e}")
    all_items.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    seen, unique = set(), []
    for it in all_items:
        key = it["title"].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(it)
    return unique[:MAX_ITEMS]


def ask_gemini(prompt):
    last_err = None
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
        try:
            out = json.loads(http(url, body, headers, timeout=120))
            parts = out["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                print(f"Model: {model}")
                return text
        except urllib.error.HTTPError as e:
            last_err = f"{model}: {e.code} {e.read().decode()[:200]}"
            print("Gemini xatosi:", last_err)
        except Exception as e:
            last_err = f"{model}: {e}"
            print("Gemini xatosi:", last_err)
    raise RuntimeError(f"Hech bir model ishlamadi. Oxirgi xato: {last_err}")


def build_prompt(items):
    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. [{it['source']}] {it['title']}\n   {it['summary']}\n   {it['link']}")
    news = "\n".join(lines)
    return f"""Sen sun'iy intellekt sohasi bo'yicha tahlilchisan. Quyida oxirgi 24-36 soatdagi AI yangiliklari ro'yxati bor.

Vazifa: shu ro'yxatdan dunyo uchun eng muhim 3 ta yangilikni tanla (bir xil voqeaning takrorlarini bitta deb hisobla; mayda mahsulot yangiliklaridan ko'ra sohaga katta ta'sir qiladiganlarini afzal ko'r).

Har bir yangilik uchun O'ZBEK tilida (oddiy, tushunarli) yoz:
- Sarlavha
- Nima bo'ldi (2-3 gap)
- Nima uchun muhim (2-3 gap)
- Keyingi oqibatlari yoki nimani kuzatish kerak (1-2 gap)
- Manba havolasi

Faqat ro'yxatdagi ma'lumotga tayan, o'zingdan fakt to'qima. Ro'yxatda aniq bo'lmagan narsani taxmin qilma. Markdown belgilarini (*, #, _) ishlatma, oddiy matn yoz. Boshiga "AI yangiliklari" deb qisqa sarlavha qo'y.

YANGILIKLAR:
{news}
"""


def send_telegram(text):
    chunks, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 > 3800:
            chunks.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    for c in chunks:
        payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": c, "disable_web_page_preview": True}).encode()
        http(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", payload, {"Content-Type": "application/json"})


def main():
    items = collect()
    print(f"Topilgan maqolalar: {len(items)}")
    if not items:
        send_telegram("Bugun yangiliklar lentalaridan maqola olib bo'lmadi. Ertaga qayta urinaman.")
        return
    try:
        send_telegram(ask_gemini(build_prompt(items)))
    except Exception as e:
        send_telegram(f"Bot xatosi: {str(e)[:500]}")
        raise


if __name__ == "__main__":
    main()
