import os
import telebot
import requests

# Get environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 'Hello! I am a weather bot. Use /weather <city> to get weather info.')

@bot.message_handler(commands=['weather'])
def send_weather(message):
    try:
        city = message.text.split()[1]
        url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric'
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            temp = data['main']['temp']
            desc = data['weather'][0]['description']
            bot.reply_to(message, f'Weather in {city}: {temp}°C, {desc}')
        else:
            bot.reply_to(message, 'City not found!')
    except IndexError:
        bot.reply_to(message, 'Please provide a city name: /weather <city>')
    except Exception as e:
        bot.reply_to(message, f'Error: {str(e)}')

if __name__ == '__main__':
    print('Bot is running...')
    bot.infinity_polling()
