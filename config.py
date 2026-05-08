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
GUILD_ID = get_env_int("GUILD_ID")

OPENROUTER_API_KEY = os.getenv("API_KEY_AI")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"