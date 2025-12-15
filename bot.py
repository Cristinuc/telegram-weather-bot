# Telegram Private Group Bot
# Limbaj: Python
# Functii: comenzi, trigger-e cu glume, vreme, analiza chat, rezumat
# Raspunde doar la comenzi si la cuvinte cheie definite
# RO / EN

import os
import re
import time
from datetime import datetime, timedelta
from collections import Counter

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))  # ID-ul grupului privat

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")  # OpenWeather
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

LANG_DEFAULT = "ro"
SUMMARY_MAX_MESSAGES = 300
SUMMARY_HOURS = 12

# trigger-e pentru glume
JOKE_TRIGGERS = [
    r"\\bpula\\b",
    r"\\bpizda\\b",
    r"\\bcoaie\\b",
    r"\\bmuie\\b",
]

JOKES = {
    "ro": [
        "Am notat. Nu ajută cu nimic.",
        "Informație procesată. Demnitatea nu.",
        "Mesaj recepționat. Inteligența rămâne opțională.",
    ],
    "en": [
        "Message received. Wisdom not detected.",
        "Logged. Improvement pending.",
        "Acknowledged. Moving on.",
    ],
}

# stocare mesaje in memorie
MESSAGES = []

# ---------------- UTILS ----------------

def detect_lang(text: str) -> str:
    ro_chars = set("ăâîșț")
    if any(c in ro_chars for c in text.lower()):
        return "ro"
    return "en"


def clean_text(text: str) -> str:
    text = re.sub(r"http\\S+", "", text)
    text = re.sub(r"[^a-zA-ZăâîșțĂÂÎȘȚ ]", " ", text)
    return text.lower()


# ---------------- HANDLERS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text(
        "Bot activ. Răspund doar la comenzi. Fără improvizații."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text(
        "/weather <oras>\\n"
        "/summary [ore] sau [nr mesaje]\\n"
        "/mood\\n"
        "/ping"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text("Sunt online. Din păcate.")


async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    if not context.args:
        await update.message.reply_text("Specifică un oraș.")
        return

    city = " ".join(context.args)
    import requests

    params = {
        "q": city,
        "appid": WEATHER_API_KEY,
        "units": "metric",
        "lang": "ro",
    }

    r = requests.get(WEATHER_URL, params=params, timeout=10)
    if r.status_code != 200:
        await update.message.reply_text("Nu găsesc orașul. Nici eu nu le știu pe toate.")
        return

    data = r.json()
    temp = data["main"]["temp"]
    desc = data["weather"][0]["description"]

    await update.message.reply_text(f"{city}. {temp}°C. {desc}.")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    now = datetime.utcnow()
    msgs = []

    if context.args:
        try:
            val = int(context.args[0])
            if val <= 24:
                since = now - timedelta(hours=val)
                msgs = [m for m in MESSAGES if m["time"] >= since]
            else:
                msgs = MESSAGES[-val:]
        except:
            pass
    else:
        since = now - timedelta(hours=SUMMARY_HOURS)
        msgs = [m for m in MESSAGES if m["time"] >= since]

    if not msgs:
        await update.message.reply_text("Nu am ce rezuma.")
        return

    words = []
    for m in msgs:
        words += clean_text(m["text"]).split()

    common = Counter(words).most_common(5)

    response = "Subiecte frecvente:\\n"
    for w, c in common:
        if len(w) > 3:
            response += f"- {w}\\n"

    await update.message.reply_text(response)


async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return

    texts = " ".join([m["text"] for m in MESSAGES[-100:]]).lower()

    negative = ["nu", "prost", "nasol", "fail", "stupid"]
    positive = ["ok", "bine", "perfect", "super"]

    score = 0
    for n in negative:
        score -= texts.count(n)
    for p in positive:
        score += texts.count(p)

    if score > 2:
        mood = "Relaxat"
    elif score < -2:
        mood = "Tensionat"
    else:
        mood = "Neutru"

    await update.message.reply_text(f"Ton general: {mood}.")


async def listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.id != GROUP_ID:
        return

    text = update.message.text or ""

    MESSAGES.append({
        "text": text,
        "time": datetime.utcnow(),
    })

    if len(MESSAGES) > 1000:
        MESSAGES.pop(0)

    for pattern in JOKE_TRIGGERS:
        if re.search(pattern, text.lower()):
            lang = detect_lang(text)
            joke = JOKES.get(lang, JOKES["ro"])
            await update.message.reply_text(joke[int(time.time()) % len(joke)])
            break


# ---------------- MAIN ----------------

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("mood", mood))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, listener))

    app.run_polling()

# ---------------- DEPLOY ----------------
# 1. Creezi botul cu BotFather si iei token-ul
# 2. Setezi variabilele de mediu BOT_TOKEN, GROUP_ID, WEATHER_API_KEY
# 3. python3 bot.py
# 4. Pentru 24/7 foloseste un VPS sau Render cu restart automat
