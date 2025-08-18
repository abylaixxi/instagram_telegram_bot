import os
import logging
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import instaloader

# Логирование
logging.basicConfig(level=logging.INFO)

# Настройки из переменных окружения
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

pending_posts = {}

# --- Хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен!")

async def fetch_instagram_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
        post = next(profile.get_posts())
        caption = post.caption if post.caption else "Без описания"
        url = post.url

        pending_posts[str(post.mediaid)] = {"caption": caption, "url": url}

        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{post.mediaid}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{post.mediaid}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await bot.send_photo(
            chat_id=MODERATOR_ID,
            photo=url,
            caption=f"Новый пост из Instagram:\n\n{caption}",
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.error(f"Ошибка при получении поста: {e}")
        await update.message.reply_text("⚠️ Не удалось получить пост.")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, post_id = query.data.split(":")
    post = pending_posts.get(post_id)

    if not post:
        await query.edit_message_caption(caption="⚠️ Пост не найден или устарел.")
        return

    if action == "approve":
        try:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=post["url"],
                caption=post["caption"]
            )
            await query.edit_message_caption(caption="✅ Пост одобрен и опубликован в канал.")
        except Exception as e:
            logging.error(f"Ошибка при одобрении поста: {e}")
            await query.edit_message_caption(caption="⚠️ Ошибка при публикации.")
    elif action == "reject":
        await query.edit_message_caption(caption="❌ Пост отклонён.")

# --- Flask webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    app_telegram.update_queue.put(update)
    return "ok"

@app.route("/")
def index():
    return "Бот работает!"

# --- Инициализация Application ---
app_telegram = ApplicationBuilder().token(BOT_TOKEN).build()
app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(CommandHandler("fetch", fetch_instagram_post))
app_telegram.add_handler(CallbackQueryHandler(button))

# Запуск Flask + Telegram
if __name__ == "__main__":
    import threading

    # Запуск бота в отдельном потоке
    threading.Thread(target=app_telegram.run_polling, daemon=True).start()

    # Запуск Flask
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
