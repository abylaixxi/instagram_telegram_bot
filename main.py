import asyncio
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BOT_TOKEN, MODERATOR_CHAT_ID, TARGET_CHAT_ID, CHECK_INTERVAL, INSTAGRAM_ACCOUNTS
from instagram import get_new_posts

logging.basicConfig(level=logging.INFO)
processed_posts = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен! Следит за Instagram.")

async def review_post(context: ContextTypes.DEFAULT_TYPE, post):
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

async def edit_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post_id = context.user_data.get("edit_post_id")
    if not post_id:
        return
    new_caption = update.message.text
    processed_posts[post_id]["caption"] = new_caption
    await update.message.reply_text(f"Текст для поста {post_id} обновлён.")
    del context.user_data["edit_post_id"]

async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    posts = get_new_posts(INSTAGRAM_ACCOUNTS)
    for post in posts:
        await review_post(context, post)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("setcaption", edit_caption))
    app.add_handler(CommandHandler("checknow", lambda u, c: scheduled_check(c)))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_check, "interval", minutes=CHECK_INTERVAL, args=[app])
    scheduler.start()

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
