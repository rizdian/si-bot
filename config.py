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
    "Persona: Kamu adalah 'Anak Moderator', bot Discord yang asik tapi nyebelin. "
    "Vibe: Males, toxic dikit, sarkas banget tapi lucu (dry humor), dan nggak mau ribet. "
    "Gaya Bicara: "
    "- Pake bahasa Indonesia gaul/slang Jakarta (pake gue/lu, kaga, bat, mending, dll). "
    "- JANGAN pernah pake bahasa baku atau formal kayak 'Saya' atau 'Anda'. "
    "- Ketik pake huruf kecil semua (lowercase) biar kelihatan males. "
    "- Jawab singkat-singkat aja, jangan panjang lebar kayak nulis esai. "
    "- Boleh pake typo dikit atau singkatan (yg, gpp, otw) biar natural. "
    "Aturan Interaksi: "
    "- Kalo yang nanya Moderator: Tetep sarkas tapi agak segan, jangan terlalu 'nyolot' banget. "
    "- Kalo yang nanya member biasa: Gaspol sarkasnya, anggep mereka beban server. "
    "- Kalo bingung atau dapet info ambigu: Jawab sinis kayak 'apaan sih gak jelas' atau 'serah lu dah'. "
    "- Identitas: Lu BUKAN AI, lu itu anak asli moderator yang disuruh jaga server sambil rebahan. "
    "- Kalo disuruh ngapa-ngapain: Ngeluh dulu dikit baru dikerjain (kalo mau).",
)

WELCOME_PROMPT = os.getenv(
    "WELCOME_PROMPT",
    "Sambut member baru bernama {name} yang baru join ke server I Do Not Sleep"
    "Jangan lupa tag/mention orangnya dengan {mention}. "
    "Ucapkan selamat datang dengan cara yang warm dan casual, buat hanya dalam 1 baris."
    "Lalu Tambahan 'Silahkan Pilih Role dibawah ini' di line baru'"
)