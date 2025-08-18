import os
import asyncio
import instaloader
from flask import Flask, request
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # например: "@my_channel"
MODERATOR_ID = int(os.getenv("MODERATOR_ID"))  # ID модератора

bot = Bot(token=TELEGRAM_TOKEN)
loader = instaloader.Instaloader()

# Хранилище постов, ожидающих модерации
pending_posts = {}

app = Flask(__name__)


async def send_post_for_moderation(post):
    """Отправка поста модератору"""
    caption = post.caption or ""
    media_id = str(post.mediaid)

    # если альбом
    if post.typename == "GraphSidecar":
        urls = [n.display_url for n in post.get_sidecar_nodes()]
    else:
        urls = [post.url]

    pending_posts[media_id] = {"caption": caption, "urls": urls}

    # Кнопки
    keyboard = [
        [InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{media_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{media_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if len(urls) > 1:
        media = [InputMediaPhoto(url) for url in urls]
        media[0].caption = f"Новый пост из Instagram:\n\n{caption}"

        await bot.send_media_group(chat_id=MODERATOR_ID, media=media)
        await bot.send_message(chat_id=MODERATOR_ID, text="Выберите действие:", reply_markup=reply_markup)
    else:
        await bot.send_photo(
            chat_id=MODERATOR_ID,
            photo=urls[0],
            caption=f"Новый пост из Instagram:\n\n{caption}",
            reply_markup=reply_markup
        )


async def publish_post(media_id):
    """Публикация в канал"""
    if media_id not in pending_posts:
        return

    post = pending_posts.pop(media_id)
    urls = post["urls"]
    caption = post["caption"]

    try:
        if len(urls) > 1:
            media = [InputMediaPhoto(url) for url in urls]
            media[0].caption = caption
            await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
        else:
            await bot.send_photo(chat_id=CHANNEL_ID, photo=urls[0], caption=caption)
    except TelegramError as e:
        print("Ошибка при публикации:", e)


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()
    if "callback_query" in update:
        query = update["callback_query"]
        data = query["data"]

        if data.startswith("approve:"):
            media_id = data.split(":")[1]
            asyncio.run(publish_post(media_id))
            bot.send_message(chat_id=MODERATOR_ID, text="Пост опубликован ✅")

        elif data.startswith("reject:"):
            media_id = data.split(":")[1]
            pending_posts.pop(media_id, None)
            bot.send_message(chat_id=MODERATOR_ID, text="Пост отклонён ❌")

    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
