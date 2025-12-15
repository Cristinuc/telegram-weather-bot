#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Private Group Bot - Compatible with python-telegram-bot v13.x"""

import os
import re
import time
import logging
from datetime import datetime, timedelta
from collections import Counter

import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

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
JOKES_RO = ["Am notat. Nu ajută cu nimic.", "Informație procesată. Demisteaza mu.", "Mesaj recepționat. Inteligenta rămâne optională."]
JOKES_EN = ["Message received. Wisdom not detected.", "Logged. Improvement pending.", "Acknowledged. Moving on."]

# Utility functions
def detect_lang(text: str) -> str:
    return "ro" if any(c in "ăâîșț" for c in text.lower()) else "en"

def clean_text(text: str) -> str:
    text = re.sub(r"https?\S+", "", text)
    text = re.sub(r"[^a-zA-ZăâîșțĂÂÎȘȚ ]", " ", text)
    return text.lower()

# Command handlers
def start(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    update.message.reply_text("Bot activ. Răspund doar la comenzi. Fără improvizații.")

def weather(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    
    if not context.args:
        update.message.reply_text("Folosire: /weather <oras>")
        return
    
    city = " ".join(context.args)
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "ro"}
    
    try:
        response = requests.get(WEATHER_URL, params=params, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            update.message.reply_text(f"Vremea în {city}: {temp}°C, {desc}")
        else:
            update.message.reply_text(f"Oraș negăsit: {city}")
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        update.message.reply_text("Eroare la obținerea vremii.")

def summary(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    
    if not MESSAGES:
        update.message.reply_text("Niciun mesaj înregistrat încă.")
        return
    
    if not context.args:
        limit = 20
    else:
        try:
            limit = int(context.args[0])
        except:
            cutoff = datetime.now() - timedelta(hours=int(context.args[0].replace("ore", "")))
            recent = [m for m in MESSAGES if m["time"] > cutoff]
            limit = len(recent)
    
    recent_msgs = MESSAGES[-limit:]
    words = []
    for msg in recent_msgs:
        words.extend(clean_text(msg["text"]).split())
    
    common = Counter(words).most_common(5)
    top_words = ", ".join([f"{w} ({c})" for w, c in common])
    
    update.message.reply_text(f"Sumar {limit} mesaje:\nCuvinte frecvente: {top_words}")

def mood(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    
    if not MESSAGES:
        update.message.reply_text("Niciun mesaj pentru analiză.")
        return
    
    recent = " ".join([m["text"] for m in MESSAGES[-10:]])
    positive = len(re.findall(r"\b(bun|super|wow|tare|cool)\b", recent, re.I))
    negative = len(re.findall(r"\b(rău|prost|nasol|urat)\b", recent, re.I))
    
    if positive > negative:
        update.message.reply_text("Mood: Pozitiv 😊")
    elif negative > positive:
        update.message.reply_text("Mood: Negativ 😞")
    else:
        update.message.reply_text("Mood: Neutru 😐")

def ping(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    update.message.reply_text("Pong! 🏓")

def gpt(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    
    if not OPENAI_API_KEY:
        update.message.reply_text("OpenAI API key nu este configurat.")
        return
    
    if not context.args:
        update.message.reply_text("Folosire: /gpt <întrebare>")
        return
    
    question = " ".join(context.args)
    
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GPT_MODEL,
            "messages": [{"role": "user", "content": question}],
            "max_tokens": 500
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", 
                               headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            update.message.reply_text(answer)
        else:
            logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
            update.message.reply_text(f"Eroare GPT: {response.status_code}")
    except Exception as e:
        logger.error(f"GPT request failed: {e}")
        update.message.reply_text("Eroare la conectarea cu GPT.")

# Message handler
def handle_message(update: Update, context: CallbackContext):
    if update.effective_chat.id != GROUP_ID:
        return
    
    msg = update.message
    if not msg or not msg.text:
        return
    
    # Store message
    MESSAGES.append({
        "text": msg.text,
        "user": msg.from_user.first_name,
        "time": datetime.now()
    })
    
    # Keep only last 1000 messages
    if len(MESSAGES) > 1000:
        MESSAGES.pop(0)
    
    # Joke trigger
    text_lower = msg.text.lower()
    for trigger in JOKE_TRIGGERS:
        if re.search(trigger, text_lower):
            lang = detect_lang(msg.text)
            joke = JOKES_RO[hash(msg.text) % len(JOKES_RO)] if lang == "ro" else JOKES_EN[hash(msg.text) % len(JOKES_EN)]
            msg.reply_text(joke)
            break

# Main
def main():
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Register handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("weather", weather))
    dp.add_handler(CommandHandler("summary", summary))
    dp.add_handler(CommandHandler("mood", mood))
    dp.add_handler(CommandHandler("ping", ping))
    dp.add_handler(CommandHandler("gpt", gpt))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Start bot
    logger.info("Bot starting...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
