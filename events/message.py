import discord
import re
import asyncio

from config import OWNER_USER_ID, AI_PERSONALITY, IS_OWNER_INACTIVE
from utils.afk import is_afk, remove_afk, get_afk, format_duration

MAINKAN_PATTERN = re.compile(r"^mainkan\s+(.+)", re.IGNORECASE)

def is_manual_mention(message: discord.Message, user_id: int) -> bool:
    return f"<@{user_id}>" in message.content or f"<@!{user_id}>" in message.content

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
            from utils.afk import is_afk as check_afk, get_afk as get_user_afk, format_duration as fmt_dur
            for mentioned in message.mentions:
                if check_afk(mentioned.id):
                    afk_info = get_user_afk(mentioned.id)
                    if afk_info:
                        dur = fmt_dur(afk_info["timestamp"])
                        reason_text = f" — *{afk_info.get('reason')}*" if afk_info.get("reason") else ""
                        await message.reply(
                            f"💤 **{mentioned.display_name}** lagi AFK ({dur}){reason_text}",
                            delete_after=10,
                        )
                        break

        # ── "mainkan <judul/link>" trigger ──────────────────────────────
        mainkan_match = MAINKAN_PATTERN.match(message.content.strip())
        if mainkan_match:
            search = mainkan_match.group(1).strip()
            member = message.author

            if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
                await message.reply("❌ Lu harus join voice channel dulu lah!")
                return

            from commands.music import do_play
            await do_play(
                search=search,
                guild=message.guild,
                voice_channel=member.voice.channel,
                send=message.channel.send,
                channel=message.channel,
                requester=member,
                client=client,
            )
            return

        # Logika untuk Owner Tag (Langit menjawab 1 kalimat)
        # if OWNER_USER_ID and is_manual_mention(message, OWNER_USER_ID):
        #     from commands.ai import ask_openrouter, ai_cooldowns
        #
        #     # Cooldown check
        #     now = asyncio.get_event_loop().time()
        #     if message.author.id in ai_cooldowns and now - ai_cooldowns[message.author.id] < 10:
        #         return
        #
        #     ai_cooldowns[message.author.id] = now
        #
        #     # Abaikan pesan yang terlalu pendek
        #     if len(message.content.strip()) < 2:
        #         return
        #
        #     # Ambil riwayat pesan (misal 5 pesan terakhir)
        #     history_lines = []
        #     async for msg in message.channel.history(limit=5, before=message):
        #         author_name = msg.author.display_name
        #         # Jika asisten yang jawab, pakai nama bot atau identitasnya
        #         name = "Lu (Tukang Ikut Campur)" if msg.author.id == client.user.id else author_name
        #         history_lines.append(f"- {name}: {msg.content}")
        #     history_lines.reverse()
        #
        #     history_text = "\n".join(history_lines) if history_lines else "Gak ada obrolan sebelumnya."
        #
        #     prompt = message.content
        #
        #     owner_unavailable = "\n\n[KONTEKS PENTING: Owner sedang tidak available/tidak online. Jawab sebagai perwakilan owner bahwa owner sedang tidak bisa merespons.]" if IS_OWNER_INACTIVE else ""
        #
        #     # Tambahkan info tentang pengirim dan target mention untuk tag
        #     author_info = f"- {message.author.display_name} (ID: {message.author.id})"
        #     # Karena ini mention owner, tambahkan info owner juga
        #     owner_member = message.guild.get_member(OWNER_USER_ID) if message.guild else None
        #     owner_name = owner_member.display_name if owner_member else "Moderator"
        #     owner_info = f"- {owner_name} (ID: {OWNER_USER_ID})"
        #
        #     # Tambahkan instruksi khusus agar jawaban hanya 1 kalimat
        #     instruction = f"\n\n(Catatan: Jawab pesan ini hanya dalam 1 kalimat saja karena kamu sedang menanggapi mention ke Owner. Ini histori singkatnya:\n{history_text}\n\nKonteks User:\n{author_info}\n{owner_info}){owner_unavailable}"
        #
        #     messages = [
        #         {"role": "system", "content": AI_PERSONALITY},
        #         {"role": "user", "content": f"{message.author.display_name}: {prompt}{instruction}"}
        #     ]
        #
        #     async with message.channel.typing():
        #         reply = await ask_openrouter(client.ai_session, messages)
        #         await message.reply(reply)
        #     return  # Berhenti di sini agar tidak memicu logika Langit bot tag di bawah jika bot juga di-tag

        # Logika Langit jika bot di-tag
        if client.user and client.user.mentioned_in(message):
            from commands.ai import ask_openrouter, ai_cooldowns
            
            # Cooldown check
            now = asyncio.get_event_loop().time()
            if message.author.id in ai_cooldowns and now - ai_cooldowns[message.author.id] < 10:
                return

            ai_cooldowns[message.author.id] = now

            # Bersihkan tag bot dari konten saat ini untuk cek panjang pesan
            prompt = message.content
            prompt = re.sub(r'<@!?%s>' % client.user.id, '', prompt).strip()

            # Abaikan pesan yang terlalu pendek atau spam
            if len(prompt) < 2 or prompt.lower() in ["w", "ok", "p", "halo", "test"]:
                # Kalau cuma ngetag doang tanpa pesan, mungkin mau nyapa, tapi kita filter biar hemat
                if not prompt: return

            # Ambil riwayat pesan (misal 5 pesan terakhir sebelum pesan ini)
            history_lines = []
            async for msg in message.channel.history(limit=5, before=message):
                content = msg.content
                # Bersihkan tag bot dari history jika ada
                content = re.sub(r'<@!?%s>' % client.user.id, '', content).strip()
                if content:
                    author_name = msg.author.display_name
                    name = "Lu (Tukang Ikut Campur)" if msg.author.id == client.user.id else author_name
                    history_lines.append(f"- {name}: {content}")
            history_lines.reverse()
            
            history_context = "Histori obrolan sebelumnya:\n" + "\n".join(history_lines) if history_lines else ""

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

    # @client.event
    # async def on_message_delete(message: discord.Message) -> None:
    #     if message.author.bot:
    #         return
    #
    #     await send_log_embed(
    #         client=client,
    #         title="🗑 MESSAGE DELETED",
    #         color=discord.Color.red(),
    #         fields=[
    #             ("👤 Author", message.author.mention, False),
    #             ("📍 Channel", message.channel.mention, True),
    #             ("💬 Content", message.content or "[Empty/Embed]", False),
    #         ],
    #     )

    # @client.event
    # async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
    #     if before.author.bot:
    #         return
    #
    #     if before.content == after.content:
    #         return
    #
    #     await send_log_embed(
    #         client=client,
    #         title="✏ MESSAGE EDITED",
    #         color=discord.Color.blue(),
    #         fields=[
    #             ("👤 Author", before.author.mention, False),
    #             ("📍 Channel", before.channel.mention, True),
    #             ("📌 Before", before.content or "[Empty]", False),
    #             ("📌 After", after.content or "[Empty]", False),
    #         ],
    #     )