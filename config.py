import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MODERATOR_CHAT_ID = int(os.getenv("MODERATOR_CHAT_ID"))
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 10))
INSTAGRAM_ACCOUNTS = [acc.strip() for acc in os.getenv("INSTAGRAM_ACCOUNTS", "").split(",") if acc.strip()]
