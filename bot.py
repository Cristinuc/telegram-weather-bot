import os
import logging
import requests
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
    
    # Adaugă handlere
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("meteo", meteo))
    
    # Pornește botul
    logger.info("Botul pornește...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
