import os
import sys
import logging
from dotenv import load_dotenv

# Force load .env and override system variables just in case
load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Fail-fast check for the Bot Token
if not BOT_TOKEN or not BOT_TOKEN.strip():
    print("❌ CRITICAL ERROR: BOT_TOKEN is missing or empty!")
    print("👉 Please ensure your .env file is in the same directory as main.py")
    print("👉 Format inside .env must be: BOT_TOKEN=1234567890:ABCdefGHIjklMNO")
    sys.exit(1)

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot_database.sqlite")

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("system.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)