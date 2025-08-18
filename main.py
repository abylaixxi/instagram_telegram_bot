import os
import logging
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import instaloader

# Логирование
logging.basicConfig(level=logging.INFO)

# Настройки из переменных окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
INSTAGRAM_LOGIN = os.getenv("INSTAGRAM_LOGIN")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")
MODERATOR_ID = int(os.getenv("MODERATOR_ID"))

bot = Bot(token=BOT_TOKEN)

app = Flask(__name__)

# Инициализация instaloader с логином
L = instaloader.Instaloader()
try:
    L.login(INSTAGRAM_LOGIN, INSTAGRAM_PASSWORD)
    logging.info(f"✅ Успешный вход в Instagram под {INSTAGRAM_LOGIN}")
except Exception as e:
    logging.error(f"⚠️ Ошибка входа в Instagram: {e}")

# Хранилище постов (вместо БД, можно расширить)
pending_posts = {}

def start(update, context):
    update.message.reply_text("Бот запущен!")

def fetch_instagram_post(update, context):
    """Команда для проверки: тянет последний пост из аккаунта"""
    try:
        profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
        post = next(profile.get_posts())

        caption = post.caption if post.caption else "Без описания"
        url = post.url

        # Сохраняем пост во временное хранилище
        pending_posts[str(post.mediaid)] = {"caption": caption, "url": url}

        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{post.mediaid}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{post.mediaid}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        bot.send_photo(
            chat_id=MODERATOR_ID,
            photo=url,
            caption=f"Новый пост из Instagram:\n\n{caption}",
            reply_markup=reply_markup
        )

    except Exception as e:
        logging.error(f"Ошибка при получении поста: {e}")
        update.message.reply_text("⚠️ Не удалось получить пост.")

def button(update, context):
    query = update.callback_query
    query.answer()

    action, post_id = query.data.split(":")
    post = pending_posts.get(post_id)

    if not post:
        query.edit_message_caption(caption="⚠️ Пост не найден или устарел.")
        return

    if action == "approve":
        try:
            bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=post["url"],
                caption=post["caption"]
            )
            query.edit_message_caption(caption="✅ Пост одобрен и опубликован в канал.")
        except Exception as e:
            logging.error(f"Ошибка при одобрении поста: {e}")
            query.edit_message_caption(caption="⚠️ Ошибка при публикации.")
    elif action == "reject":
        query.edit_message_caption(caption="❌ Пост отклонён.")

# Flask webhook
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    dp.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Бот работает!"

# Настройка Telegram dispatcher
from telegram.ext import Updater
updater = Updater(token=BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("fetch", fetch_instagram_post))  # для теста
dp.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
