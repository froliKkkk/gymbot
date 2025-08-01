import os
from dotenv import load_dotenv
import json

load_dotenv()

# Telegram settings
TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_IDS = [int(x) for x in os.getenv("ALLOWED_USER_IDS").split(",")]


# Google Sheets settings
def get_google_creds():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDS")
    return json.loads(creds_json) if creds_json else None
