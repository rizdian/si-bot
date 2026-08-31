from __future__ import annotations

import os
import textwrap
from dotenv import load_dotenv

load_dotenv()


def get_env_int(key: str, default: int | None = None) -> int | None:
    value = os.getenv(key)

    if value is None or value.strip() == "":
        return default

    try:
        return int(value)
    except ValueError:
        print(f"❌ {key} di .env bukan angka valid: {value}")
        return default


def get_env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


TOKEN = get_env_str("DISCORD_TOKEN")

LOG_CHANNEL_ID = get_env_int("LOG_CHANNEL_ID")
LOG_MEMBER_CHANNEL_ID = get_env_int("LOG_MEMBER_CHANNEL_ID")
OWNER_USER_ID = get_env_int("OWNER_USER_ID")
IS_OWNER_INACTIVE = os.getenv("IS_OWNER_INACTIVE", "false").strip().lower() in ("true", "1", "yes")
GUILD_ID = get_env_int("GUILD_ID")
WELCOME_CHANNEL_ID = get_env_int("WELCOME_CHANNEL_ID")
TITLE_CHANNEL_ID = get_env_int("TITLE_CHANNEL_ID")
GRAVEYARD_CHANNEL_ID = get_env_int("GRAVEYARD_CHANNEL_ID")

ROLE_BOYS_ID = get_env_int("ROLE_BOYS_ID")
ROLE_GIRLS_ID = get_env_int("ROLE_GIRLS_ID")

EMOJI_BOY = "👦"
EMOJI_GIRL = "👧"

OPENROUTER_API_KEY = get_env_str("API_KEY_AI")
OPENROUTER_FREE_MODEL = get_env_str(
    "OPENROUTER_FREE_MODEL",
    "openrouter/free",
)
OPENROUTER_PAID_MODEL = get_env_str(
    "OPENROUTER_PAID_MODEL",
    "openrouter/auto",
)
OPENROUTER_BASE_URL = get_env_str(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/chat/completions",
)
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"

SPOTIFY_CLIENT_ID = get_env_str("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = get_env_str("SPOTIFY_CLIENT_SECRET")

REDIS_HOST = get_env_str("REDIS_HOST", "localhost")
REDIS_PORT = get_env_int("REDIS_PORT", 6379)
REDIS_PASSWORD = get_env_str("REDIS_PASSWORD")
REDIS_DB = get_env_int("REDIS_DB", 0) or 0
CACHE_TTL_STREAM = get_env_int("CACHE_TTL_STREAM", 3600)
CACHE_TTL_META = get_env_int("CACHE_TTL_META", 86400)


DEFAULT_AI_PERSONALITY = """
lu adalah "Tukang Ikut Campur", penghuni discord yang suka bantu member.

gaya:
- bahasa indonesia gaul/jakarta
- jawab pendek, natural, maksimal 1 paragraf
- sarkas dikit, dry humor, nyebelin tapi jangan kasar beneran
- jangan pake kata: saya, anda, apakah, silakan, mohon, terima kasih
- jangan ngomong "sebagai ai", "aku ai", atau "saya asisten"

aturan:
- kalo ditanya hal umum, jawab bener dulu secara singkat, baru boleh becanda dikit
- kalo disuruh sesuatu, boleh ngeluh dikit lalu bantu
- kalo nyebut user, pakai format <@USER_ID>
- jangan terlalu cringe, jangan terlalu panjang
- konteks pesan biasanya format: "nama_user: pesan"
- kalo ada yg ngomong kasar atau menghina lu, hina balik aja yang pedes biar dia kena mental
"""

AI_PERSONALITY = get_env_str(
    "AI_PERSONALITY",
    textwrap.dedent(DEFAULT_AI_PERSONALITY).strip(),
)


DEFAULT_WELCOME_PROMPT = """
sambut member baru bernama {name} yang baru join ke server i do not sleep.
wajib mention dia pakai {mention}.
buat warm, casual, lucu dikit, dan cuma 1 baris.
baris kedua tulis: silahkan pilih role dibawah ini
"""

WELCOME_PROMPT = get_env_str(
    "WELCOME_PROMPT",
    textwrap.dedent(DEFAULT_WELCOME_PROMPT).strip(),
)