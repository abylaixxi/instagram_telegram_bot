import os
import logging
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, filters, ConversationHandler
)
import instaloader
import asyncio

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
last_post_id = None  # чтобы не отправлять один и тот же пост

# -----------------------------
# Conversation states
# -----------------------------
EDIT_CAPTION = 1

# -----------------------------
# Функция проверки Instagram
# -----------------------------
async def check_instagram(context: ContextTypes.DEFAULT_TYPE):
    global last_post_id
    try:
        profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
        post = next(profile.get_posts())  # последний пост

        if str(post.mediaid) == last_post_id:
            return  # пост уже отправлялся, ничего не делаем

        last_post_id = str(post.mediaid)
        caption = post.caption or "Без описания"
        url = post.url

        # Сохраняем во временное хранилище
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

# -----------------------------
# Хэндлеры Telegram
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен и каждые 5 минут проверяет Instagram!")

# approve/reject
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
            logging.error(f"Ошибка при публикации: {e}")
            await query.edit_message_caption(caption="⚠️ Ошибка при публикации.")
    elif action == "reject":
        await query.edit_message_caption(caption="❌ Пост отклонён.")

# -----------------------------
# ConversationHandler для редактирования
# -----------------------------
async def start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    post_id = query.data.split(":")[1]
    context.user_data["editing_post_id"] = post_id
    await query.edit_message_caption(caption="✏️ Отправь новый текст для поста.")
    return EDIT_CAPTION

async def receive_edited_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_id = context.user_data.get("editing_post_id")
    if not post_id or post_id not in pending_posts:
        await update.message.reply_text("⚠️ Пост не найден или устарел.")
        return ConversationHandler.END

    new_caption = update.message.text
    pending_posts[post_id]["caption"] = new_caption

    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{post_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{post_id}"),
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit:{post_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_photo(
        chat_id=MODERATOR_ID,
        photo=pending_posts[post_id]["url"],
        caption=f"✏️ Отредактированный пост:\n\n{new_caption}",
        reply_markup=reply_markup
    )

    await update.message.reply_text("✅ Текст поста обновлён и отправлен модератору.")
    return ConversationHandler.END

# -----------------------------
# Инициализация Application
# -----------------------------
app_telegram = ApplicationBuilder().token(BOT_TOKEN).build()
app_telegram.add_handler(CommandHandler("start", start))
app_telegram.add_handler(CallbackQueryHandler(button, pattern="^(approve|reject):"))

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit, pattern="^edit:")],
    states={EDIT_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edited_caption)]},
    fallbacks=[]
)
app_telegram.add_handler(conv_handler)

# добавляем задачу каждые 5 минут
job_queue = app_telegram.job_queue
job_queue.run_repeating(check_instagram, interval=300, first=5)

# -----------------------------
# Flask webhook
# -----------------------------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(app_telegram.process_update(update))
    return "ok"

@app.route("/")
def index():
    return "Бот работает!"

if __name__ == "__main__":
    asyncio.run(app_telegram.run_polling())
