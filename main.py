import os
import telebot
from flask import Flask, request
import instaloader

# Загружаем токен и URL
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")

if not BOT_TOKEN:
    raise ValueError("❌ Переменная окружения BOT_TOKEN не установлена!")
if not APP_URL:
    raise ValueError("❌ Переменная окружения APP_URL не установлена!")

bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)

L = instaloader.Instaloader()

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Привет! Напиши username Instagram, и я попробую достать его профиль.")

@bot.message_handler(func=lambda msg: True)
def get_instagram(message):
    username = message.text.strip()
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        reply = (
            f"📸 Имя: {profile.full_name}\n"
            f"📝 Биография: {profile.biography}\n"
            f"👥 Подписчиков: {profile.followers}\n"
            f"➡️ Ссылка: https://instagram.com/{username}"
        )
        bot.reply_to(message, reply)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

# Webhook endpoint
@server.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

# Главная страница — ставим webhook
@server.route("/", methods=["GET"])
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{BOT_TOKEN}")
    return "Webhook установлен!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Запуск на порту {port}, BOT_TOKEN начинается с {BOT_TOKEN[:5]}...")
    server.run(host="0.0.0.0", port=port)
