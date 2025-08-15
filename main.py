import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Bot

# ==== НАСТРОЙКИ ====
BOT_TOKEN = os.getenv("BOT_TOKEN")  # токен Telegram бота
CHAT_ID = os.getenv("CHAT_ID")      # твой Telegram ID
INSTAGRAM_ACCOUNTS = ["test_bot_for_niyet2"]        # без @
CHECK_INTERVAL = 60                 # каждые X секунд

# ==== ЛОГИ ====
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=BOT_TOKEN)

# Хранилище последних постов, чтобы не слать дубликаты
last_posts = {}

def get_latest_post(username):
    url = f"https://www.instagram.com/{username}/"
    logging.info(f"🔍 Проверка аккаунта: {username}")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/115.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=10)

        logging.info(f"🌐 Статус-код: {r.status_code}, Размер HTML: {len(r.text)} байт")

        if len(r.text) < 5000:
            logging.warning("⚠ Похоже, Instagram вернул заглушку или капчу. Парсинг невозможен.")
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        script_tag = soup.find("script", text=lambda t: t and "window._sharedData" in t)

        if not script_tag:
            logging.warning("⚠ Не удалось найти данные о постах в HTML.")
            return None

        shared_data = script_tag.string.split(" = ", 1)[1].rstrip(";")
        import json
        data = json.loads(shared_data)

        edges = data["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_owner_to_timeline_media"]["edges"]

        if not edges:
            logging.warning("⚠ Посты не найдены.")
            return None

        latest_shortcode = edges[0]["node"]["shortcode"]
        post_url = f"https://www.instagram.com/p/{latest_shortcode}/"

        logging.info(f"✅ Найден последний пост: {post_url}")
        return post_url

    except Exception as e:
        logging.error(f"❌ Ошибка при получении поста: {e}")
        return None

def check_accounts():
    for username in INSTAGRAM_ACCOUNTS:
        post_url = get_latest_post(username)
        if post_url and last_posts.get(username) != post_url:
            last_posts[username] = post_url
            bot.send_message(chat_id=CHAT_ID, text=f"🆕 Новый пост в @{username}:\n{post_url}")

if __name__ == "__main__":
    logging.info("🚀 Бот запущен!")
    while True:
        check_accounts()
        time.sleep(CHECK_INTERVAL)
