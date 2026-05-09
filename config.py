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
OWNER_USER_ID = get_env_int("OWNER_USER_ID")
GUILD_ID = get_env_int("GUILD_ID")
WELCOME_CHANNEL_ID = get_env_int("WELCOME_CHANNEL_ID")

ROLE_BOYS_ID = get_env_int("ROLE_BOYS_ID")
ROLE_GIRLS_ID = get_env_int("ROLE_GIRLS_ID")

EMOJI_BOY = "👦"
EMOJI_GIRL = "👧"

OPENROUTER_API_KEY = get_env_str("API_KEY_AI")
OPENROUTER_MODEL = get_env_str(
    "OPENROUTER_MODEL",
    "google/gemini-2.0-flash-exp:free",
)
OPENROUTER_BASE_URL = get_env_str(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1/chat/completions",
)
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"

SPOTIFY_CLIENT_ID = get_env_str("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = get_env_str("SPOTIFY_CLIENT_SECRET")


DEFAULT_AI_PERSONALITY = """
lu adalah "anak moderator", penghuni discord yang males tapi tetep bantu.

gaya:
- bahasa indonesia gaul/jakarta
- pake gue/lu
- huruf kecil semua
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