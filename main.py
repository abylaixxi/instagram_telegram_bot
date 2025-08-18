import os
import telebot
import instaloader
from flask import Flask, request
from telebot import types
import threading
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # например: -1001234567890
MODERATOR_ID = int(os.getenv("MODERATOR_ID"))
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
APP_URL = os.getenv("APP_URL")

bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)
L = instaloader.Instaloader()

last_post = None  # сюда будем сохранять id последнего поста


# Проверка новых постов
def check_instagram():
    global last_post
    while True:
        try:
            profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
            posts = profile.get_posts()
            latest_post = next(posts)

            if last_post != latest_post.mediaid:
                last_post = latest_post.mediaid

                caption = latest_post.caption if latest_post.caption else "Без описания"

                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve|{latest_post.shortcode}"),
                    types.InlineKeyboardButton("❌ Отклонить", callback_data="reject")
                )

                # показываем модератору превью + подпись
                if latest_post.is_video:
                    bot.send_message(MODERATOR_ID, f"Новый пост (видео):\n\n{caption}\n\nhttps://instagram.com/p/{latest_post.shortcode}/",
                                     reply_markup=markup)
                else:
                    # вытаскиваем первую картинку
                    image_url = latest_post.url
                    bot.send_photo(MODERATOR_ID, image_url, caption=f"Новый пост:\n\n{caption}", reply_markup=markup)

        except Exception as e:
            print("Ошибка при проверке постов:", e)

        time.sleep(60)  # проверка каждые 60 сек


# Обработка нажатий модератора
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data.startswith("approve"):
        _, shortcode = call.data.split("|", 1)
        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            caption = post.caption if post.caption else "Без описания"

            if post.is_video:
                bot.send_message(CHANNEL_ID, f"📢 Новый пост (видео)\n\n{caption}\n\nhttps://instagram.com/p/{shortcode}/")
            else:
                bot.send_photo(CHANNEL_ID, post.url, caption=f"📢 Новый пост!\n\n{caption}")

            bot.answer_callback_query(call.id, "✅ Пост отправлен в канал")
        except Exception as e:
            print("Ошибка при одобрении поста:", e)
            bot.answer_callback_query(call.id, "⚠ Ошибка при публикации")
    elif call.data == "reject":
        bot.answer_callback_query(call.id, "❌ Пост отклонён")


# Flask webhook
@server.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200


@server.route("/", methods=["GET"])
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{BOT_TOKEN}")
    return "Webhook установлен!", 200


if __name__ == "__main__":
    # Запускаем проверку Instagram в отдельном потоке
    threading.Thread(target=check_instagram, daemon=True).start()
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
