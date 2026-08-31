import discord
import re

from config import OWNER_USER_ID, AI_PERSONALITY, IS_OWNER_INACTIVE
from utils.afk import is_afk, remove_afk, get_afk, format_duration
from commands.ai import ask_openrouter, is_on_cooldown

MAINKAN_PATTERN = re.compile(r"^mainkan\s+(.+)", re.IGNORECASE)

MIN_PROMPT_LEN = 2
SPAM_WORDS = {"w", "ok", "p", "halo", "test"}


def is_manual_mention(message: discord.Message, user_id: int) -> bool:
    return f"<@{user_id}>" in message.content or f"<@!{user_id}>" in message.content


def strip_mention(text: str, user_id: int) -> str:
    return re.sub(rf"<@!?{user_id}>", "", text).strip()


async def build_history_lines(
    channel: discord.abc.Messageable,
    before: discord.Message,
    limit: int,
    bot_id: int,
    strip_bot_mention: bool = False,
) -> str:
    lines = []

    async for msg in channel.history(limit=limit, before=before):
        content = msg.content
        if strip_bot_mention:
            content = strip_mention(content, bot_id)
        if not content:
            continue
        name = "Lu (Tukang Ikut Campur)" if msg.author.id == bot_id else msg.author.display_name
        lines.append(f"- {name}: {content}")

    lines.reverse()
    return "\n".join(lines)

def register_message_events(client: discord.Client):
    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        # ── Remove AFK when user sends a message ─────────────────────────
        if isinstance(message.author, discord.Member) and is_afk(message.author.id):
            afk_data = remove_afk(message.author.id)
            if afk_data and message.guild:
                original_nick = afk_data.get("original_nick")
                try:
                    await message.author.edit(nick=original_nick)
                except (discord.Forbidden, discord.HTTPException):
                    pass
                await message.reply(
                    f"👋 Welcome back {message.author.mention}! AFK lu udah dihapus.",
                    delete_after=5,
                )

        # ── Notify when mentioning an AFK user ───────────────────────────
        if message.guild and message.mentions:
            for mentioned in message.mentions:
                if is_afk(mentioned.id):
                    afk_info = get_afk(mentioned.id)
                    if afk_info:
                        dur = format_duration(afk_info["timestamp"])
                        reason_text = f" — *{afk_info.get('reason')}*" if afk_info.get("reason") else ""
                        await message.reply(
                            f"💤 **{mentioned.display_name}** lagi AFK ({dur}){reason_text}",
                            delete_after=10,
                        )
                        break

        if message.mention_everyone or "@everyone" in message.content or "@here" in message.content:
            return

        if OWNER_USER_ID and is_manual_mention(message, OWNER_USER_ID):
            cooldown, _ = is_on_cooldown(message.author.id)
            if cooldown or len(message.content.strip()) < MIN_PROMPT_LEN:
                return

            history_text = await build_history_lines(message.channel, message, 2, client.user.id)
            history_text = history_text or "Gak ada obrolan sebelumnya."

            prompt = message.content

            owner_unavailable = "\n\n[KONTEKS PENTING: Owner sedang tidak available/tidak online. Jawab sebagai perwakilan owner bahwa owner sedang tidak bisa merespons.]" if IS_OWNER_INACTIVE else ""

            # Tambahkan info tentang pengirim dan target mention untuk tag
            author_info = f"- {message.author.display_name} (ID: {message.author.id})"
            # Karena ini mention owner, tambahkan info owner juga
            owner_member = message.guild.get_member(OWNER_USER_ID) if message.guild else None
            owner_name = owner_member.display_name if owner_member else "Moderator"
            owner_info = f"- {owner_name} (ID: {OWNER_USER_ID})"

            # Tambahkan instruksi khusus agar jawaban hanya 1 kalimat
            instruction = f"\n\n(Catatan: Jawab pesan ini hanya dalam 1 kalimat saja karena kamu sedang menanggapi mention ke Owner. Ini histori singkatnya:\n{history_text}\n\nKonteks User:\n{author_info}\n{owner_info}){owner_unavailable}"

            messages = [
                {"role": "system", "content": AI_PERSONALITY},
                {"role": "user", "content": f"{message.author.display_name}: {prompt}{instruction}"}
            ]

            async with message.channel.typing():
                reply = await ask_openrouter(client.ai_session, messages)
                await message.reply(reply)
            return  # Berhenti di sini agar tidak memicu logika Langit bot tag di bawah jika bot juga di-tag

        if client.user and client.user.mentioned_in(message):
            cooldown, _ = is_on_cooldown(message.author.id)
            if cooldown:
                return

            prompt = strip_mention(message.content, client.user.id)

            if len(prompt) < MIN_PROMPT_LEN or prompt.lower() in SPAM_WORDS:
                if not prompt:
                    return

            history_lines = await build_history_lines(
                message.channel, message, 2, client.user.id, strip_bot_mention=True
            )
            history_context = f"Histori obrolan sebelumnya:\n{history_lines}" if history_lines else ""

            # Sertakan nama pengirim saat ini juga
            prompt_with_author = f"{message.author.display_name}: {prompt}" if prompt else "Halo"

            # Ambil konteks jika ada mention lain
            context_parts = []
            # Tambahkan info tentang pengirim pesan saat ini
            context_parts.append(f"- {message.author.display_name} (ID: {message.author.id}) adalah pengirim pesan saat ini.")
            
            user_ids = re.findall(r"<@!?(\d+)>", prompt)
            
            for user_id in set(user_ids):
                if int(user_id) == client.user.id:
                    continue
                    
                member = message.guild.get_member(int(user_id)) if message.guild else None
                if member:
                    roles = [role.name.lower() for role in member.roles]
                    category = "umum"
                    if any("mod" in r for r in roles) or any("admin" in r for r in roles):
                        category = "moderator"
                    elif any("boy" in r for r in roles):
                        category = "boys"
                    elif any("girl" in r for r in roles):
                        category = "girls"
                    
                    context_parts.append(f"- {member.display_name} (ID: {user_id}) adalah seorang {category}.")

            system_content = AI_PERSONALITY
            if context_parts:
                context = "\n".join(context_parts)
                system_content += f"\n\nKonteks tambahan tentang member yang di-mention:\n{context}"
            
            if history_context:
                system_content += f"\n\n{history_context}"

            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt_with_author}
            ]
            
            async with message.channel.typing():
                reply = await ask_openrouter(client.ai_session, messages)
                await message.reply(reply)