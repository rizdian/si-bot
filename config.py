import os
from dotenv import load_dotenv

load_dotenv()


def get_env_int(key: str):
    value = os.getenv(key)
    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        print(f"❌ {key} di .env bukan angka valid!")
        return None


TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = get_env_int("LOG_CHANNEL_ID")
OWNER_USER_ID = get_env_int("OWNER_USER_ID")