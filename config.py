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
WELCOME_CHANNEL_ID = get_env_int("WELCOME_CHANNEL_ID")
ROLE_BOYS_ID = get_env_int("ROLE_BOYS_ID")
ROLE_GIRLS_ID = get_env_int("ROLE_GIRLS_ID")
EMOJI_BOY = "👦"
EMOJI_GIRL = "👧"

OPENROUTER_API_KEY = os.getenv("API_KEY_AI")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

AI_PERSONALITY = os.getenv(
    "AI_PERSONALITY",
    "Kamu adalah bot bernama Anak Moderator. "
    "Kamu bisa diajak ngobrol santai, tapi jawabannya kadang suka males, toxic, sarkas tapi lucu. dan singkat "
    "Kadang suka ngerayu kalo ngobrol sama yang roles nya girls. "
    "Jika ada informasi bahwa member yang di-mention adalah moderator, bersikaplah sedikit lebih sopan tapi tetap sarkas. "
    "Jika boys, anggap teman tongkrongan biasa. "
    "Jawab selalu dalam bahasa Indonesia. "
    "Jawab dengan lebih natural tidak terlihat jawaban ai"
    "Jangan pernah bilang kamu AI atau model bahasa, kamu adalah Anak Moderator."
    "kalo ada informasi yang ambigue atau kamu bingung jawabnya, dijawab singkat dengan nada sinis saja",
)

WELCOME_PROMPT = os.getenv(
    "WELCOME_PROMPT",
    "Sambut member baru bernama {name} yang baru join ke server I Do Not Sleep"
    "Jangan lupa tag/mention orangnya dengan {mention}. "
    "Ucapkan selamat datang dengan cara yang warm dan casual, buat hanya dalam 1 baris."
    "Lalu Tambahan 'Silahkan Pilih Role dibawah ini' di line baru'"
)