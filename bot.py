#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Private Group Bot - Compatible with python-telegram-bot v20.x"""

import os
import re
import time
import logging
from datetime import datetime, timedelta
from collections import Counter
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Constants
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
GPT_MODEL = "gpt-4o-mini"

# In-memory storage
MESSAGES = []

# Joke triggers and responses
JOKE_TRIGGERS = [r"\bpula\b", r"\bpizda\b", r"\bcoaie\b", r"\bmuie\b"]
JOKES_RO = ["Am notat. Nu ajută cu nimic.", "Informație procesată. Demnitatea nu.", "Mesaj recepționat. Inteligența rămâne opțională."]
JOKES_EN = ["Message received. Wisdom not detected.", "Logged. Improvement pending.", "Acknowledged. Moving on."]

# Health check server
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    def log_message(self, format, *args):
        pass

# Utility functions
def detect_lang(text: str) -> str:
    return "ro" if any(c in "ăâîșț" for c in text.lower()) else "en"

def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-zA-ZăâîșțĂÂÎȘȚ ]", " ", text)
    return text.lower()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text("Bot activ. Răspund doar la comenzi. Fără improvizații.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    await update.message.reply_text("/weather <oras>\n/summary [ore|nr]\n/mood\n/gpt <intrebare>\n/ping")

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
    try:
        r = requests.get(WEATHER_URL, params={"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "ro"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            await update.message.reply_text(f"{city}. {data['main']['temp']}°C. {data['weather'][0]['description']}.")
        else:
            await update.message.reply_text("Nu găsesc orașul.")
    except:
        await update.message.reply_text("Eroare la obținerea vremii.")

async def gpt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    if not OPENAI_API_KEY:
        await update.message.reply_text("GPT nu e configurat.")
        return
    if not context.args:
        await update.message.reply_text("Scrie ceva după /gpt.")
        return
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(model=GPT_MODEL, messages=[{"role": "user", "content": " ".join(context.args)}], max_tokens=200)
        await update.message.reply_text(resp.choices[0].message.content)
    except Exception as e:
        await update.message.reply_text(f"Eroare GPT: {str(e)[:100]}")

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
        since = now - timedelta(hours=12)
        msgs = [m for m in MESSAGES if m["time"] >= since]
    if not msgs:
        await update.message.reply_text("Nu am ce rezuma.")
        return
    words = []
    for m in msgs:
        words += clean_text(m["text"]).split()
    common = Counter(words).most_common(5)
    response = "Subiecte frecvente:\n" + "\n".join([f"- {w}" for w, c in common if len(w) > 3])
    await update.message.reply_text(response)

async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_ID:
        return
    texts = " ".join([m["text"] for m in MESSAGES[-100:]]).lower()
    score = sum(-texts.count(n) for n in ["nu", "prost", "nasol", "fail", "stupid"]) + sum(texts.count(p) for p in ["ok", "bine", "perfect", "super"])
    mood_str = "Relaxat" if score > 2 else ("Tensionat" if score < -2 else "Neutru")
    await update.message.reply_text(f"Ton general: {mood_str}.")

async def listener(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.effective_chat.id != GROUP_ID:
        return
    text = update.message.text or ""
    MESSAGES.append({"text": text, "time": datetime.utcnow()})
    if len(MESSAGES) > 1000:
        MESSAGES.pop(0)
    for pattern in JOKE_TRIGGERS:
        if re.search(pattern, text.lower()):
            lang = detect_lang(text)
            jokes = JOKES_RO if lang == "ro" else JOKES_EN
            await update.message.reply_text(jokes[int(time.time()) % len(jokes)])
            break

def main():
    # Start HTTP health check server
    port = int(os.getenv("PORT", "10000"))
    httpd = HTTPServer(('0.0.0.0', port), HealthHandler)
    Thread(target=httpd.serve_forever, daemon=True).start()
    logger.info(f"Health check server running on port {port}")

    # Build application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("weather", weather))
    app.add_handler(CommandHandler("gpt", gpt_cmd))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("mood", mood))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, listener))

    # Run
    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
