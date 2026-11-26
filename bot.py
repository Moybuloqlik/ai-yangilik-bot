import os
import json
import html
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DRY_RUN = os.environ.get("DRY_RUN") == "1"

# Ixtiyoriy: haqiqiy Telegram stikerlari. Kun raqami (0=dushanba ... 6=yakshanba) -> sticker file_id
# Bo'sh qoldirsangiz, stikersiz, faqat emojilar bilan yuboriladi.
STICKERS = {
    # 0: "CAACAgIAAxkBA....",
}

MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
          "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
DAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]

PARA_TIMES = {1: "08:00 – 09:20", 2: "09:30 – 10:50", 3: "11:00 – 12:20"}

SUBJECT_EMOJI = {
    "Matematika": "📐",
    "Akademik ko'nikmalar va kasbiy kompetentlik": "🎯",
    "Iqtisodiyotda axborot texnologiyalari va tizimlari": "💻",
    "Madaniyat": "🎭",
    "Iqtisodiyot nazariyasi": "📈",
    "Biznesga kirish": "💼",
    "Xorijiy til": "🌍",
}

# (para raqami, fan, turi, xona)
SCHEDULE = {
    0: [(1, "Matematika", "ma'ruza", "3-bino · 514-xona"),
        (2, "Akademik ko'nikmalar va kasbiy kompetentlik", "amaliy", "2-bino · 322-xona"),
        (3, "Iqtisodiyotda axborot texnologiyalari va tizimlari", "ma'ruza", "3-bino · 514-xona")],
    1: [(1, "Madaniyat", "", "2-bino · 313-xona"),
        (2, "Iqtisodiyot nazariyasi", "amaliy", "2-bino · 513-xona"),
        (3, "Biznesga kirish", "amaliy", "2-bino · 413-xona")],
    2: [(2, "Iqtisodiyotda axborot texnologiyalari va tizimlari", "amaliy", "3-bino · 404-xona"),
        (3, "Akademik ko'nikmalar va kasbiy kompetentlik", "ma'ruza", "3-bino · 106-xona")],
    3: [(1, "Biznesga kirish", "ma'ruza", "2-bino · 511-xona"),
        (2, "Xorijiy til", "amaliy", "1-bino · 305 yoki 306-xona"),
        (3, "Xorijiy til", "amaliy", "1-bino · 305 yoki 306-xona")],
    4: [(1, "Iqtisodiyot nazariyasi", "ma'ruza", "3-bino · 514-xona"),
        (2, "Matematika", "amaliy", "3-bino · 209-xona")],
}

HEADERS = {
    0: ("🌅", "Yangi hafta — toza sahifa"),
    1: ("☕", "Ritm topildi, davom"),
    2: ("🌿", "Haftaning yarmi ortda"),
    3: ("⚡", "Yakunga bir qadam qoldi"),
    4: ("🎉", "Juma — oxirgi yuz metr"),
    5: ("🏃", "Yugurish kuni"),
    6: ("🌤", "Yengil yugurish va tiklanish"),
}

QUOTES = {
    0: "Katta natija — har kuni qilingan kichik ishlardan quriladi.",
    1: "Intizom — motivatsiya tugagan joyda ishlaydigan narsa.",
    2: "To'xtamasdan sekin yurish — to'xtab-to'xtab yugurishdan yaxshi.",
    3: "Bugungi harakat — kelgusi haftaning ishonchi.",
    4: "Haftani chiroyli yoping, dam olish haq qilingan bo'ladi.",
}

LINE = "━━━━━━━━━━━━━━━━━━"


def e(s):
    return html.escape(s, quote=False)


def day_message(wd, now):
    emoji, title = HEADERS[wd]
    date_txt = f"{now.day}-{MONTHS[now.month - 1]}"
    head = f"{emoji} <b>{DAYS[wd]}</b>  ·  {date_txt}\n<i>{e(title)}</i>\n{LINE}\n"

    if wd >= 5:
        if wd == 5:
            body = (
                "\n🏃‍♂️ <b>Bugun yugurish kuni!</b>\n\n"
                "▫️ Krossovka va qulay kiyimni tayyorlang\n"
                "▫️ Yugurishdan oldin 5-10 daqiqa razminka\n"
                "▫️ Suv olishni unutmang 💧\n"
                "▫️ Tezlik emas, barqarorlik muhim\n"
            )
            quote = "Eng qiyin qadam — eshikdan chiqish. Qolgani o'zi bo'ladi."
        else:
            body = (
                "\n🏃‍♂️ <b>Bugun ham yugurish kuni!</b>\n\n"
                "▫️ Kecha charchagan bo'lsangiz, sekinroq yuguring\n"
                "▫️ Yugurgach cho'zilish mashqlarini qiling\n"
                "▫️ Kechqurun ertangi dars uchun sumkani tayyorlab qo'ying 🎒\n"
            )
            quote = "Dam olish ham rejaning bir qismi. Ertaga yangi hafta."
        return head + body + f"\n{LINE}\n💬 <i>{e(quote)}</i>"

    lessons = SCHEDULE[wd]
    first_para = lessons[0][0]
    start = PARA_TIMES[first_para].split(" – ")[0]
    count = len(lessons)
    intro = f"\n🎒 Bugun <b>{count} ta para</b>, boshlanishi <b>{start}</b> da\n"
    if first_para > 1:
        intro += "😌 <i>Ertalab biroz ko'proq vaqtingiz bor</i>\n"
    out = head + intro

    for para, subject, kind, room in lessons:
        icon = SUBJECT_EMOJI.get(subject, "📘")
        kind_txt = f" <i>({e(kind)})</i>" if kind else ""
        out += (
            f"\n<b>{para}-para</b>  ·  🕘 {PARA_TIMES[para]}\n"
            f"{icon} {e(subject)}{kind_txt}\n"
            f"📍 {e(room)}\n"
        )

    last_para = lessons[-1][0]
    end = PARA_TIMES[last_para].split(" – ")[1]
    out += f"\n{LINE}\n🏁 Darslar <b>{end}</b> da tugaydi\n💬 <i>{e(QUOTES[wd])}</i>"
    return out


def tg(method, payload):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    now = datetime.now(ZoneInfo("Asia/Tashkent"))
    test_day = os.environ.get("TEST_DAY", "").strip()
    wd = int(test_day) if test_day.isdigit() and 0 <= int(test_day) <= 6 else now.weekday()
    text = day_message(wd, now)
    if DRY_RUN:
        print(text)
        return
    if wd in STICKERS:
        tg("sendSticker", {"chat_id": CHAT_ID, "sticker": STICKERS[wd]})
    tg("sendMessage", {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True})


if __name__ == "__main__":
    main()
