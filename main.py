import os
import telebot
from telebot import types
import instaloader
from flask import Flask, request

# -----------------------------
# Конфигурация
# -----------------------------
TOKEN = os.getenv("BOT_TOKEN")  # токен бота
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # id канала (например, -1001234567890)
MODERATOR_ID = int(os.getenv("MODERATOR_ID"))  # id модератора

INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")  # ник аккаунта

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# -----------------------------
# Авторизация в Instagram
# -----------------------------
L = instaloader.Instaloader()
try:
    # Если нужен логин/пароль, можно добавить
    # L.login(os.getenv("INSTAGRAM_LOGIN"), os.getenv("INSTAGRAM_PASSWORD"))
    profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
    print(f"✅ Успешное подключение к профилю {INSTAGRAM_USER}")
except Exception as e:
    print("⚠️ Ошибка входа в Instagram:", e)

# -----------------------------
# Получение новых постов
# -----------------------------
def get_latest_post():
    profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
    post = next(profile.get_posts())  # самый новый пост
    return post

# -----------------------------
# Отправляем модератору пост
# -----------------------------
def send_post_for_moderation():
    post = get_latest_post()
    caption = post.caption if post.caption else "Без описания"
    shortcode = post.shortcode

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve|{shortcode}|{caption}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data="reject")
    )

    bot.send_message(
        MODERATOR_ID,
        f"📢 Новый пост из Instagram:\n\n{caption}\n\nhttps://instagram.com/p/{shortcode}/",
        reply_markup=markup
    )

# -----------------------------
# Обработка кнопок
# -----------------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data.startswith("approve"):
        try:
            _, shortcode, caption = call.data.split("|", 2)
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            media_url = post.url  # ссылка на фото

            bot.send_photo(CHANNEL_ID, media_url, caption=f"📢 Новый пост!\n\n{caption}")
            bot.answer_callback_query(call.id, "✅ Пост отправлен в канал")
        except Exception as e:
            print("Ошибка при одобрении поста:", e)
            bot.answer_callback_query(call.id, "⚠️ Ошибка при отправке поста")
    elif call.data == "reject":
        bot.answer_callback_query(call.id, "❌ Пост отклонён")

# -----------------------------
# Flask Webhook для Railway
# -----------------------------
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Бот работает!", 200

# -----------------------------
# Тестовый запуск (один раз при старте)
# -----------------------------
with app.app_context():
    send_post_for_moderation()

# -----------------------------
# Запуск сервера
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
