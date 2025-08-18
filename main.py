import os
import json
import telebot
import instaloader
import time
from flask import Flask, request
from threading import Thread

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # например: "@my_channel"
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")  # username аккаунта, с которого берем посты

bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)
L = instaloader.Instaloader()

# === Работа с JSON ===
POSTS_FILE = "posts.json"

def load_posts():
    if os.path.exists(POSTS_FILE):
        with open(POSTS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posts(posts):
    with open(POSTS_FILE, "w") as f:
        json.dump(list(posts), f)

posted = load_posts()

# === Проверка новых постов ===
def check_instagram():
    while True:
        try:
            profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
            for post in profile.get_posts():
                if post.shortcode not in posted:
                    text = f"📸 Новый пост у {INSTAGRAM_USER}!\n\n{post.url}"
                    # Отправляем модератору (тебе в личку)
                    bot.send_message(os.getenv("MODERATOR_ID"), text,
                                     reply_markup=moderation_keyboard(post.shortcode, post.url))
                    posted.add(post.shortcode)
                    save_posts(posted)
                    break  # проверяем только последний пост
        except Exception as e:
            print("Ошибка проверки:", e)
        time.sleep(60)  # проверять раз в минуту

# === Кнопки для модерации ===
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def moderation_keyboard(shortcode, url):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve|{shortcode}|{url}"),
        InlineKeyboardButton("❌ Пропустить", callback_data=f"skip|{shortcode}")
    )
    return kb

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    action = call.data.split("|")[0]
    shortcode = call.data.split("|")[1]
    if action == "approve":
        url = call.data.split("|")[2]
        bot.send_message(CHANNEL_ID, f"📢 Новый пост!\n{url}")
        bot.answer_callback_query(call.id, "✅ Опубликовано")
    elif action == "skip":
        bot.answer_callback_query(call.id, "❌ Пропущено")

# === Flask webhook ===
@server.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

@server.route("/", methods=["GET"])
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{os.getenv('APP_URL')}/{BOT_TOKEN}")
    return "Webhook установлен!", 200

# === Фоновый поток проверки ===
def run_checker():
    t = Thread(target=check_instagram, daemon=True)
    t.start()

if __name__ == "__main__":
    run_checker()
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
