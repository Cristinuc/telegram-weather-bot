import os
import logging
import requests
import json
from datetime import datetime, timedelta
import asyncio
from typing import Optional, Dict, List
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandlApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Configurare logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Încărcare variabile de mediu
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Fișier pentru stocare reminders
REMINDERS_FILE = "reminders.json"

# Global dict pentru reminders active
reminders_data: Dict[str, List[Dict]] = {}


def get_weather(city: str) -> dict:
    """Obține datele meteo de la OpenWeather API."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "ro"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Eroare la obținerea datelor meteo: {e}")
        raise


def summarize_with_perplexity(text: str) -> str:
    """Generează un rezumat folosind Perplexity API."""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "user",
                "content": f"Rezumă pe scurt, în română, această descriere meteo pentru un utilizator de Telegram (maxim 2-3 propoziții):\n\n{text}"
            }
        ],
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Eroare la apelul Perplexity API: {e}")
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pentru comanda /start."""
    welcome_message = (
        "Bun venit! 👋\n\n"
        "Sunt un bot meteo inteligent. Folosește comanda:\n"
        "/meteo <oraș> - pentru a obține informații despre vreme\n\n"
        "Exemplu: /meteo București"
    )
    await update.message.reply_text(welcome_message)


async def meteo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pentru comanda /meteo."""
    if not context.args:
        await update.message.reply_text(
            "Te rog specifică un oraș.\n"
            "Exemplu: /meteo Cluj-Napoca"
        )
        return
    
    city = " ".join(context.args)
    
    try:
        # Trimite mesaj de așteptare
        status_message = await update.message.reply_text("🔍 Caut informații meteo...")
        
        # Obține datele meteo
        weather_data = get_weather(city)
        
        # Extrage informațiile relevante
        temp = weather_data["main"]["temp"]
        feels_like = weather_data["main"]["feels_like"]
        humidity = weather_data["main"]["humidity"]
        description = weather_data["weather"][0]["description"]
        wind_speed = weather_data["wind"]["speed"]
        
        # Creează textul de bază
        base_text = (
            f"Vremea în {city}:\n"
            f"🌡️ Temperatură: {temp}°C (se simte ca {feels_like}°C)\n"
            f"☁️ Condiții: {description}\n"
            f"💨 Vânt: {wind_speed} m/s\n"
            f"💧 Umiditate: {humidity}%"
        )
        
        # Actualizează mesajul
        await status_message.edit_text("🤖 Generez rezumat inteligent...")
        
        # Generează rezumat cu Perplexity
        summary = summarize_with_perplexity(base_text)
        
        # Trimite răspunsul final
        final_message = f"{base_text}\n\n📝 Rezumat:\n{summary}"
        await status_message.edit_text(final_message)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            await update.message.reply_text(
                f"❌ Orașul '{city}' nu a fost găsit.\n"
                "Verifică numele și încearcă din nou."
            )
        else:
            await update.message.reply_text(
                "❌ A apărut o eroare la obținerea datelor meteo.\n"
                "Te rog încearcă din nou mai târziu."
            )
        logger.error(f"HTTP Error: {e}")
    except Exception as e:
        await update.message.reply_text(
            "❌ A apărut o eroare neașteptată.\n"
            "Te rog încearcă din nou."
        )
        logger.exception(f"Eroare neașteptată: {e}")



# Lista de cuvinte trigger pentru glume picante
SPICY_WORDS = ["pula", "pizda", "coaie", "muie", "tzatze", "tate", "cur", "pizdă", "pulă", "țâțe"]


def contains_spicy_word(text: str) -> bool:
    """Verifică dacă textul conține cuvinte picante."""
    text_lower = text.lower()
    return any(word in text_lower for word in SPICY_WORDS)


def generate_spicy_joke() -> str:
    """Generează o glumă picantă/sexy/ironică folosind Perplexity AI."""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "user",
                "content": "Spune-mi o glumă scurtă în română, cu tentă sexy și ironică, în stilul comedianților stand-up. Fii creative, nu vulgară excesiv, dar picantă și amuzantă (maxim 2-3 propoziții)."
            }
        ],
        "max_tokens": 200,
        "temperature": 0.9
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        logger.error(f"Eroare la generarea glumei: {e}")
        return "😏 Hmm, mi-a scăpat gluma... dar poți încerca din nou!"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pentru mesaje text care detectează cuvinte picante."""
    if not update.message or not update.message.text:
        return
    
    message_text = update.message.text
    
    # Verifică dacă mesajul conține cuvinte picante
    if contains_spicy_word(message_text):
        # Trimite mesaj de așteptare
        status_msg = await update.message.reply_text("😏 Hehe, văd că ești în formă... las' că am ceva pentru tine!")
        
        try:
            # Generează glumă picantă
            joke = generate_spicy_joke()
            await status_msg.edit_text(f"🔥 {joke}")
        except Exception as e:
            logger.exception(f"Eroare la trimiterea glumei: {e}")
            await status_msg.edit_text("😅 Ups, mi-a scăpat gluma... încearcă din nou!")


    
    # ============= REMINDER SYSTEM =============

def load_reminders() -> Dict:
    """Încarcă reminders din fișier JSON."""
    try:
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.error(f"Eroare la încărcarea reminders: {e}")
        return {}


def save_reminders():
    """Salvează reminders în fișier JSON."""
    try:
        with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(reminders_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Eroare la salvarea reminders: {e}")


def parse_time_input(time_str: str) -> Optional[datetime]:
    """Parse input de timp în diverse formate."""
    time_str = time_str.strip().lower()
    now = datetime.now()
    
    # Format: "în X ore/minute"
    if "în" in time_str:
        try:
            if "ore" in time_str or "oră" in time_str:
                hours = int(''.join(filter(str.isdigit, time_str)))
                return now + timedelta(hours=hours)
            elif "min" in time_str:
                minutes = int(''.join(filter(str.isdigit, time_str)))
                return now + timedelta(minutes=minutes)
        except:
            pass
    
    # Format: "HH:MM"
    try:
        time_parts = time_str.split(":")
        if len(time_parts) == 2:
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target
    except:
        pass
    
    return None


async def reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler pentru comanda /reminder."""
    if not context.args:
        help_text = (
            "🔔 **Cum se folosește /reminder**\n\n"
            "**Format:**\n"
            "`/reminder <timp> <mesaj> [@user]`\n\n"
            "**Exemple de timp:**\n"
            "• `10:00` - Azi la 10:00\n"
            "• `19:30` - Azi la 19:30\n"
            "• `în 2 ore` - Peste 2 ore\n"
            "• `în 30 min` - Peste 30 minute\n\n"
            "**Exemple:**\n"
            "`/reminder 10:00 Standup meeting`\n"
            "`/reminder 19:00 Repetiție trupă @john`\n"
            "`/reminder în 2 ore Verifică mixul`\n\n"
            "Vezi toate: `/listreminders`\n"
            "Șterge: `/deletereminder <id>`"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    # Parse argumentele
    args_text = " ".join(context.args)
    
    # Extrage timpul (primul argument)
    time_input = context.args[0]
    if len(context.args) > 1 and context.args[1] in ["ore", "oră", "min", "minute"]:
        time_input = f"{context.args[0]} {context.args[1]}"
        message_start = 2
    else:
        message_start = 1
    
    # Parse timpul
    target_time = parse_time_input(time_input)
    if not target_time:
        await update.message.reply_text("❌ Format de timp invalid. Încearcă: `10:00`, `în 2 ore`, `în 30 min`", parse_mode='Markdown')
        return
    
    # Extrage mesajul
    if len(context.args) <= message_start:
        await update.message.reply_text("❌ Lipsește mesajul reminder-ului.")
        return
    
    reminder_message = " ".join(context.args[message_start:])
    
    # Extrage user mention (dacă există)
    target_user = None
    if "@" in reminder_message:
        # Găsește primul @username
        import re
        mentions = re.findall(r'@\w+', reminder_message)
        if mentions:
            target_user = mentions[0]
    
    # Creează reminder object
    chat_id = str(update.effective_chat.id)
    reminder_id = f"{chat_id}_{int(target_time.timestamp())}"
    
    reminder_obj = {
        "id": reminder_id,
        "chat_id": chat_id,
        "message": reminder_message,
        "time": target_time.isoformat(),
        "target_user": target_user,
        "created_by": update.effective_user.username or update.effective_user.first_name,
        "recurring": None  # Pentru viitor: daily, weekly, etc.
    }
    
    # Salvează în global dict
    if chat_id not in reminders_data:
        reminders_data[chat_id] = []
    reminders_data[chat_id].append(reminder_obj)
    save_reminders()
    
    # Confirmă
    time_str = target_time.strftime("%H:%M, %d.%m.%Y")
    confirm = f"✅ Reminder setat pentru **{time_str}**\n✉️ Mesaj: {reminder_message}"
    if target_user:
        confirm += f"\n👤 Pentru: {target_user}"
    
    await update.message.reply_text(confirm, parse_mode='Markdown')


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Listează toate reminders active pentru chat."""
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in reminders_data or not reminders_data[chat_id]:
        await update.message.reply_text("📦 Nu există reminders active pentru acest chat.")
        return
    
    # Sortează după timp
    sorted_reminders = sorted(reminders_data[chat_id], key=lambda x: x['time'])
    
    text = "🔔 **Reminders Active:**\n\n"
    for idx, rem in enumerate(sorted_reminders, 1):
        time_dt = datetime.fromisoformat(rem['time'])
        time_str = time_dt.strftime("%H:%M, %d.%m")
        text += f"{idx}. **{time_str}** - {rem['message'][:50]}"
        if rem.get('target_user'):
            text += f" ({rem['target_user']})"
        text += f"\n   ID: `{rem['id']}`\n\n"
    
    text += "\nȘterge cu: `/deletereminder <id>`"
    await update.message.reply_text(text, parse_mode='Markdown')


async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Șterge un reminder după ID."""
    if not context.args:
        await update.message.reply_text("❌ Specifică ID-ul reminder-ului: `/deletereminder <id>`", parse_mode='Markdown')
        return
    
    reminder_id = context.args[0]
    chat_id = str(update.effective_chat.id)
    
    if chat_id not in reminders_data:
        await update.message.reply_text("❌ Nu există reminders pentru acest chat.")
        return
    
    # Caută și șterge
    initial_count = len(reminders_data[chat_id])
    reminders_data[chat_id] = [r for r in reminders_data[chat_id] if r['id'] != reminder_id]
    
    if len(reminders_data[chat_id]) < initial_count:
        save_reminders()
        await update.message.reply_text("✅ Reminder șters cu succes!")
    else:
        await update.message.reply_text("❌ Reminder ID invalid sau inexistent.")


async def check_reminders(application):
    """Task care verifică periodic reminder-urile și le trimite."""
    while True:
        try:
            now = datetime.now()
            
            for chat_id, reminders in list(reminders_data.items()):
                for reminder in reminders[:]:
                    reminder_time = datetime.fromisoformat(reminder['time'])
                    
                    # Dacă timpul a sosit (cu tolerance de 1 minut)
                    if now >= reminder_time and (now - reminder_time).seconds < 120:
                        # Trimite reminder
                        message = f"🔔 **REMINDER**\n\n{reminder['message']}"
                        if reminder.get('target_user'):
                            message = f"{reminder['target_user']} {message}"
                        
                        try:
                            await application.bot.send_message(
                                chat_id=int(chat_id),
                                text=message,
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Eroare la trimiterea reminder: {e}")
                        
                        # Șterge reminder (dacă nu e recurring)
                        if not reminder.get('recurring'):
                            reminders_data[chat_id].remove(reminder)
                            save_reminders()
            
            # Așteaptă 30 secunde înainte de următoarea verificare
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.exception(f"Eroare în check_reminders: {e}")
            await asyncio.sleep(60)

def main():
    """Funcția principală care pornește botul."""
    # Verifică variabilele de mediu
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nu este setat în variabilele de mediu")
    if not OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY nu este setat în variabilele de mediu")
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY nu este setat în variabilele de mediu")
    
    # Creează aplicația
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        # Încarcă reminders din fișier
    global reminders_data
    reminders_data = load_reminders()
    
    # Adaugă handlere
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("meteo", meteo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("reminder", reminder))
    application.add_handler(CommandHandler("listreminders", list_reminders))
    application.add_handler(CommandH
                            
                                # Start reminder checker în background
    asyncio.create_task(check_reminders(application))andler("deletereminder", delete_reminder))
    
    # Pornește botul
    logger.info("Botul pornește...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
