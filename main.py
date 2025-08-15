import os
import time
import requests
import telebot

# --- Конфиг из переменных окружения Railway ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # токен твоего Telegram-бота
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")      # ключ RapidAPI
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")  # имя Instagram-аккаунта
MODERATOR_CHAT_ID = int(os.getenv("MODERATOR_CHAT_ID"))  # chat_id модератора
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 60))    # интервал проверки в секундах

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Запоминаем уже опубликованные посты
posted_ids = set()

def get_latest_post():
    """Запрос к RapidAPI для получения последнего поста"""
    url = "https://instagram-scraper-stable-api.p.rapidapi.com/ig_get_fb_profile_hover.php"
    querystring = {"username_or_url": INSTAGRAM_USERNAME}
    headers = {
        "x-rapidapi-host": "instagram-scraper-stable-api.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code != 200:
        print(f"Ошибка API: {response.status_code} {response.text}")
        return None

    data = response.json()
    try:
        # Берём первый пост из массива
        post = data["posts"][0]
        return {
            "id": post["id"],
            "caption": post.get("caption", ""),
            "image_url": post["image_url"]
        }
    except Exception as e:
        print(f"Ошибка обработки данных: {e}")
        return None

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    """Обработка кнопок модерации"""
    if call.data.startswith("approve_"):
        post_id = call.data.split("_", 1)[1]
        bot.send_message(call.message.chat.id, f"✅ Пост {post_id} одобрен и опубликован!")
        # Здесь можно отправить пост в основной канал или чат
    elif call.data.startswith("reject_"):
        post_id = call.data.split("_", 1)[1]
        bot.send_message(call.message.chat.id, f"❌ Пост {post_id} отклонён.")

def send_for_moderation(post):
    """Отправка поста модератору на подтверждение"""
    keyboard = telebot.types.InlineKeyboardMarkup()
    approve_btn = telebot.types.InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{post['id']}")
    reject_btn = telebot.types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{post['id']}")
    keyboard.add(approve_btn, reject_btn)

    bot.send_photo(
        MODERATOR_CHAT_ID,
        post["image_url"],
        caption=f"Новый пост:\n{post['caption']}",
        reply_markup=keyboard
    )

def check_new_posts():
    """Цикл проверки Instagram на новые посты"""
    while True:
        post = get_latest_post()
        if post and post["id"] not in posted_ids:
            posted_ids.add(post["id"])
            send_for_moderation(post)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    import threading
    # Запускаем проверку постов в отдельном потоке
    threading.Thread(target=check_new_posts, daemon=True).start()
    print("🚀 Бот запущен и ждёт новые посты...")
    bot.infinity_polling()
