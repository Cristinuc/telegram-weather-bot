import os
import logging
import requests
import json
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackContext,
    filters,
)

# Configurare logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Încărcare variabile de mediu
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Reminder storage & timezone
REMINDERS_FILE = "reminders.json"
DEFAULT_TZ = "Europe/Bucharest"
CHAT_TIMEZONES = {}


def load_reminders() -> list:
    if not os.path.exists(REMINDERS_FILE):
        return []
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Eroare la citirea {REMINDERS_FILE}: {e}")
        return []


def save_reminders(reminders: list) -> None:
    try:
        with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Eroare la scrierea {REMINDERS_FILE}: {e}")


def get_chat_timezone(chat_id: int) -> ZoneInfo:
    tz_name = CHAT_TIMEZONES.get(str(chat_id), DEFAULT_TZ)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def parse_date_time(date_str: str, time_str: str, tz: ZoneInfo) -> datetime:
    try:
        if "." in date_str:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        else:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
            raise ValueError(            "Format dată/oră invalid. Folosește: DD-MM-YYYY HH:MM sau DD.MM.YYYY HH:MM, ex: 20-12-2025 10:00"
            )
            return dt.replace(tzinfo=tz)


def parse_time_only(time_str: str, tz: ZoneInfo) -> time:
    try:
        t = datetime.strptime(time_str, "%H:%M").time()
        return t
    except ValueError:
        raise ValueError("Format oră invalid. Folosește HH:MM, ex: 10:00.")


def get_weather(city: str) -> dict:
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "ro",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Eroare la obținerea datelor meteo: {e}")
        raise


def summarize_with_perplexity(text: str) -> str:
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
                "content": (
                    "Rezumă pe scurt, în română, această descriere meteo pentru un utilizator "
                    "de Telegram (maxim 2-3 propoziții):\n\n"
                    f"{text}"
                ),
            }
        ],
        "max_tokens": 150,
        "temperature": 0.7,
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
    welcome_message = (
        "Bun venit! 👋\n\n"
        "Sunt un bot meteo inteligent. Folosește comenzile:\n"
        "/meteo <oraș> - pentru a obține informații despre vreme\n"
        "/reminder ... - pentru a seta memento-uri în grup\n\n"
        "Exemplu: /meteo București"
    )
    await update.message.reply_text(welcome_message)


async def meteo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Te rog specifică un oraș.\n"
            "Exemplu: /meteo Cluj-Napoca"
        )
        return

    city = " ".join(context.args)

    try:
        status_message = await update.message.reply_text("🔍 Caut informații meteo...")

        weather_data = get_weather(city)

        temp = weather_data["main"]["temp"]
        feels_like = weather_data["main"]["feels_like"]
        humidity = weather_data["main"]["humidity"]
        description = weather_data["weather"][0]["description"]
        wind_speed = weather_data["wind"]["speed"]

        base_text = (
            f"Vremea în {city}:\n"
            f"🌡️ Temperatură: {temp}°C (se simte ca {feels_like}°C)\n"
            f"☁️ Condiții: {description}\n"
            f"💨 Vânt: {wind_speed} m/s\n"
            f"💧 Umiditate: {humidity}%"
        )

        await status_message.edit_text("🤖 Generez rezumat inteligent...")

        summary = summarize_with_perplexity(base_text)

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


SPICY_WORDS = ["pula", "pizda", "coaie", "muie", "tzatze", "tate", "cur", "pizdă", "pulă", "țâțe"]


def contains_spicy_word(text: str) -> bool:
    text_lower = text.lower()
    return any(word in text_lower for word in SPICY_WORDS)


def generate_spicy_joke() -> str:
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
                "content": (
                    "Spune-mi o glumă scurtă în română, cu tentă sexy și ironică, "
                    "în stilul comedianilor stand-up. Fii creativă, nu vulgară excesiv, "
                    "dar picantă și amuzantă (maxim 2-3 propoziții)."
                ),
            }
        ],
        "max_tokens": 200,
        "temperature": 0.9,
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
    if not update.message or not update.message.text:
        return

    message_text = update.message.text

    if contains_spicy_word(message_text):
        status_msg = await update.message.reply_text(
            "😏 Hehe, văd că ești în formă... las' că am ceva pentru tine!"
        )

        try:
            joke = generate_spicy_joke()
            await status_msg.edit_text(f"🔥 {joke}")
        except Exception as e:
            logger.exception(f"Eroare la trimiterea glumei: {e}")
            await status_msg.edit_text("😅 Ups, mi-a scăpat gluma... încearcă din nou!")


async def reminder_job(context: CallbackContext) -> None:
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    scope = job_data["scope"]
    message = job_data["message"]
    target_user_id = job_data.get("target_user_id")
    target_username = job_data.get("target_username")

    mention = ""
    if scope == "user":
        if target_username:
            mention = f"@{target_username} "
        elif target_user_id:
            mention = f'<a href="tg://user?id={target_user_id}"></a> '

    text = f"{mention}{message}"

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        disable_notification=False,
    )


async def reminder_job_monthly_wrapper(context: CallbackContext) -> None:
    job_data = context.job.data
    monthly_day = job_data.get("monthly_day")
    now = datetime.now(ZoneInfo("UTC")).astimezone()
    if now.day == monthly_day:
        await reminder_job(context)


def schedule_reminder(application, reminder: dict):
    jq = application.job_queue
    job_name = reminder["job_name"]
    chat_id = reminder["chat_id"]
    tz_utc = ZoneInfo("UTC")
    job_data = {
        "chat_id": chat_id,
        "scope": reminder["scope"],
        "message": reminder["message"],
        "target_user_id": reminder.get("target_user_id"),
        "target_username": reminder.get("target_username"),
    }

    if reminder["type"] == "once":
        run_at = datetime.fromisoformat(reminder["run_at"]).replace(tzinfo=tz_utc)
        jq.run_once(reminder_job, when=run_at, name=job_name, data=job_data)

    elif reminder["type"] == "interval":
        seconds = reminder["interval_seconds"]
        jq.run_repeating(
            reminder_job,
            interval=seconds,
            first=datetime.fromisoformat(reminder["run_at"]).replace(tzinfo=tz_utc),
            name=job_name,
            data=job_data,
        )

    elif reminder["type"] == "daily":
        run_at = datetime.fromisoformat(reminder["run_at"]).astimezone(tz_utc)
        jq.run_daily(
            reminder_job,
            time=time(run_at.hour, run_at.minute),
            name=job_name,
            data=job_data,
        )

    elif reminder["type"] == "weekly":
        run_at = datetime.fromisoformat(reminder["run_at"]).astimezone(tz_utc)
        jq.run_daily(
            reminder_job,
            time=time(run_at.hour, run_at.minute),
            days=tuple(reminder["days_of_week"]),
            name=job_name,
            data=job_data,
        )

    elif reminder["type"] == "monthly":
        run_at = datetime.fromisoformat(reminder["run_at"]).astimezone(tz_utc)
        job_data["monthly_day"] = run_at.day
        jq.run_daily(
            reminder_job_monthly_wrapper,
            time=time(run_at.hour, run_at.minute),
            name=job_name,
            data=job_data,
        )


def load_and_schedule_all(application):
    reminders = load_reminders()
    for r in reminders:
        try:
            schedule_reminder(application, r)
        except Exception as e:
            logger.error(f"Eroare la programarea reminder-ului {r.get('id')}: {e}")


async def reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    text = update.message.text.strip()
    args = text.split(maxsplit=1)
    if len(args) < 2:
        await update.message.reply_text(
            "Sintaxă:\n"
            "/reminder grup \"mesaj\" 2025-12-20 10:00\n"
            "/reminder @user \"mesaj\" 2025-12-20 10:00\n"
            "/reminder grup \"mesaj\" zilnic 10:00\n"
            "/reminder @user \"mesaj\" în 2 ore"
            "/reminder grup \"mesaj\" 20-12-2025 10:00\n"
            "/reminder @user \"mesaj\" 20-12-2025 10:00\n"
            "/reminder grup \"mesaj\" zilnic 10:00\n"    rest = args[1].strip()

    if rest.startswith("grup"):
        scope = "group"
        rest = rest[len("grup"):].strip()
        target_user_id = None
        target_username = None
    elif rest.startswith("@"):
        scope = "user"
        first_space = rest.find(" ")
        if first_space == -1:
            await update.message.reply_text("Specifică și mesajul și timpul după username.")
            return
        target_username = rest[1:first_space]
        rest = rest[first_space:].strip()
        target_user_id = None
    else:
        await update.message.reply_text("Specifică 'grup' sau @user după /reminder.")
        return

    if not rest.startswith('"'):
        await update.message.reply_text(
            "Mesajul trebuie pus între ghilimele duble, ex: \"Standup la 10:00\"."
        )
        return

    closing_quote = rest.find('"', 1)
    if closing_quote == -1:
        await update.message.reply_text("Mesajul nu este închis cu ghilimele.")
        return

    message_text = rest[1:closing_quote].strip()
    tail = rest[closing_quote + 1 :].strip()

    if not message_text:
        await update.message.reply_text("Mesajul nu poate fi gol.")
        return

    tz = get_chat_timezone(chat_id)

    try:
        reminder_obj = await build_reminder_object(
            update,
            context,
            chat_id,
            scope,
            target_user_id,
            target_username,
            message_text,
            tail,
            tz,
        )
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    reminders = load_reminders()

    for r in reminders:
        if (
            r["chat_id"] == reminder_obj["chat_id"]
            and r["message"] == reminder_obj["message"]
            and r["type"] == reminder_obj["type"]
            and r["run_at"] == reminder_obj["run_at"]
        ):
            await update.message.reply_text("Un reminder identic este deja setat. Evit duplicatul.")
            return

    new_id = max([r["id"] for r in reminders], default=0) + 1
    reminder_obj["id"] = new_id
    reminders.append(reminder_obj)
    save_reminders(reminders)

    schedule_reminder(context.application, reminder_obj)

    await update.message.reply_text(f"✅ Reminder setat (ID {new_id}).")


async def build_reminder_object(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    scope: str,
    target_user_id: int | None,
    target_username: str | None,
    message_text: str,
    tail: str,
    tz: ZoneInfo,
) -> dict:
    tail_parts = tail.split()

    if tail_parts and tail_parts[0].lower() == "în":
        if len(tail_parts) != 3:
            raise ValueError("Folosește formatul: în <număr> ore/minute.")
        try:
            num = int(tail_parts[1])
        except ValueError:
            raise ValueError("Numărul pentru interval trebuie să fie întreg.")
        unit = tail_parts[2].lower()
        if unit.startswith("or"):
            delta = timedelta(hours=num)
        elif unit.startswith("min"):
            delta = timedelta(minutes=num)
        else:
            raise ValueError("Unitatea suportată: ore sau minute.")
        now = datetime.now(tz)
        run_at_local = now + delta
        run_at_utc = run_at_local.astimezone(ZoneInfo("UTC"))
        return {
            "chat_id": chat_id,
            "scope": scope,
            "target_user_id": target_user_id,
            "target_username": target_username,
            "message": message_text,
            "type": "interval",
            "run_at": run_at_utc.isoformat(),
            "interval_seconds": int(delta.total_seconds()),
            "days_of_week": None,
            "job_name": f"rem_interval_{chat_id}_{int(run_at_utc.timestamp())}",
        }

    if tail_parts and tail_parts[0].lower() == "zilnic":
        if len(tail_parts) != 2:
            raise ValueError("Folosește: zilnic HH:MM")
        t = parse_time_only(tail_parts[1], tz)
        now = datetime.now(tz)
        first_run = datetime.combine(now.date(), t, tzinfo=tz)
        if first_run <= now:
            first_run = first_run + timedelta(days=1)
        run_at_utc = first_run.astimezone(ZoneInfo("UTC"))
        return {
            "chat_id": chat_id,
            "scope": scope,
            "target_user_id": target_user_id,
            "target_username": target_username,
            "message": message_text,
            "type": "daily",
            "run_at": run_at_utc.isoformat(),
            "interval_seconds": None,
            "days_of_week": None,
            "job_name": f"rem_daily_{chat_id}_{int(run_at_utc.timestamp())}",
        }

    if len(tail_parts) != 2:
        raise ValueError("Folosește: <data> <ora>, ex: 2025-12-20 10:00")
    date_str, time_str = tail_parts
    dt_local = parse_date_time(date_str, time_str, tz)
    if dt_local <= datetime.now(tz):
        raise ValueError("Folosește: <data> <ora>, ex: 20-12-2025 10:00")
        run_at_utc = dt_local.astimezone(ZoneInfo("UTC"))
    return {
        "chat_id": chat_id,
        "scope": scope,
        "target_user_id": target_user_id,
        "target_username": target_username,
        "message": message_text,
        "type": "once",
        "run_at": run_at_utc.isoformat(),
        "interval_seconds": None,
        "days_of_week": None,
        "job_name": f"rem_once_{chat_id}_{int(run_at_utc.timestamp())}",
    }


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN nu este setat în variabilele de mediu")
    if not OPENWEATHER_API_KEY:
        raise RuntimeError("OPENWEATHER_API_KEY nu este setat în variabilele de mediu")
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY nu este setat în variabilele de mediu")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        async def post_init(application):
        load_and_schedule_all(application)

    application.post_init = post_init


    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("meteo", meteo))
    application.add_handler(CommandHandler("reminder", reminder))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Botul pornește...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
