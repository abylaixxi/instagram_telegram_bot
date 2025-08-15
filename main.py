import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BOT_TOKEN, MODERATOR_CHAT_ID, TARGET_CHAT_ID, CHECK_INTERVAL, INSTAGRAM_ACCOUNTS
from instagram import get_new_posts

# Логирование
logging.basicConfig(level=logging.INFO)

# Память для уже обработанных постов
processed_posts = {}


# ===== Команды =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен! Следит за Instagram.")


async def review_post(context: ContextTypes.DEFAULT_TYPE, post):
    """Отправка поста модератору для проверки"""
    keyboard = [
        [InlineKeyboardButton("✅ Опубликовать", callback_data=f"approve|{post['id']}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject|{post['id']}")],
        [InlineKeyboardButton("✏ Редактировать", callback_data=f"edit|{post['id']}")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    if post["is_video"]:
        await context.bot.send_video(
            chat_id=MODERATOR_CHAT_ID,
            video=post["media_url"],
            caption=post["caption"],
            reply_markup=markup
        )
    else:
        await context.bot.send_photo(
            chat_id=MODERATOR_CHAT_ID,
            photo=post["media_url"],
            caption=post["caption"],
            reply_markup=markup
        )

    processed_posts[post["id"]] = post


# ===== Обработка кнопок =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, post_id = query.data.split("|")
    post = processed_posts.get(post_id)

    if not post:
        await query.edit_message_caption(caption="❌ Пост не найден.")
        return

    if action == "approve":
        await context.bot.send_photo(
            chat_id=TARGET_CHAT_ID,
            photo=post["media_url"],
            caption=post["caption"]
        )
        await query.edit_message_caption(caption="✅ Пост опубликован!")
    elif action == "reject":
        await query.edit_message_caption(caption="🚫 Пост отклонён.")
    elif action == "edit":
        await query.message.reply_text(f"✏ Введите новый текст для поста {post_id}")
        context.user_data["edit_post_id"] = post_id


# ===== Редактирование текста =====
async def edit_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_id = context.user_data.get("edit_post_id")
    if not post_id:
        return
    new_caption = update.message.text
    processed_posts[post_id]["caption"] = new_caption
    await update.message.reply_text(f"✅ Текст для поста {post_id} обновлён.")
    del context.user_data["edit_post_id"]


# ===== Проверка Instagram =====
async def scheduled_check(app: Application):
    posts = get_new_posts(INSTAGRAM_ACCOUNTS)
    for post in posts:
        await review_post(app, post)


# ===== Запуск =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, edit_caption))

    # Планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_check, "interval", minutes=CHECK_INTERVAL, args=[app])
    scheduler.start()

    logging.info("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
