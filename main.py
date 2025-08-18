import os
import logging
import asyncio
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
import instaloader

# -----------------------------
# Логирование
# -----------------------------
logging.basicConfig(level=logging.INFO)

# -----------------------------
# Переменные окружения
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
INSTAGRAM_USER = os.getenv("INSTAGRAM_USER")
MODERATOR_ID = int(os.getenv("MODERATOR_ID"))

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# -----------------------------
# Instaloader (без логина)
# -----------------------------
L = instaloader.Instaloader()

# -----------------------------
# Хранилище постов
# -----------------------------
pending_posts = {}

# -----------------------------
# Состояние редактирования
# -----------------------------
EDIT_CAPTION = range(1)

# -----------------------------
# Хэндлеры Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен!")

async def fetch_instagram_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
        post = next(profile.get_posts())

        caption = post.caption or "Без описания"
        url = post.url

        pending_posts[str(post.mediaid)] = {"caption": caption, "url": url}

        keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{post.mediaid}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{post.mediaid}"),
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit:{post.mediaid}")
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
        return ConversationHandler.END

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
    elif action == "edit":
        context.user_data["edit_post_id"] = post_id
        await query.edit_message_caption(caption="✏️ Отправьте новый текст для поста:")
        return EDIT_CAPTION

async def edit_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_id = context.user_data.get("edit_post_id")
    if not post_id or post_id not in pending_posts:
        await update.message.reply_text("⚠️ Пост не найден или устарел.")
        return ConversationHandler.END

    new_caption = update.message.text
    pending_posts[post_id]["caption"] = new_caption
    await update.message.reply_text("✅ Текст поста обновлён.")
    return ConversationHandler.END

# -----------------------------
# Инициализация Application
# -----------------------------
app_telegram = ApplicationBuilder().token(BOT_TOKEN).build()
app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(CommandHandler("fetch", fetch_instagram_post))

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button, pattern="^edit:", per_message=True)],
    states={
        EDIT_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_caption)]
    },
    fallbacks=[]
)
app_telegram.add_handler(CallbackQueryHandler(button))
app_telegram.add_handler(conv_handler)

# -----------------------------
# Долгоживущий event loop для Flask
# -----------------------------
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    loop.create_task(app_telegram.process_update(update))
    return "ok"

@app.route("/")
def index():
    return "Бот работает!"

# -----------------------------
# Запуск polling для локальной проверки
# -----------------------------
if __name__ == "__main__":
    loop.create_task(app_telegram.run_polling())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
