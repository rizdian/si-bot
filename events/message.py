import discord
import re

from config import OWNER_USER_ID, AI_PERSONALITY
from utils.logger import send_log_embed


def is_manual_mention(message: discord.Message, user_id: int) -> bool:
    return f"<@{user_id}>" in message.content or f"<@!{user_id}>" in message.content

def register_message_events(client: discord.Client):
    @client.event
    async def on_message(message: discord.Message) -> None:
        if message.author.bot:
            return

        # Logika untuk Owner Tag (AI menjawab 1 kalimat)
        if OWNER_USER_ID and is_manual_mention(message, OWNER_USER_ID):
            from commands.ai import ask_openrouter
            
            # Ambil riwayat pesan (misal 5 pesan terakhir)
            history_lines = []
            async for msg in message.channel.history(limit=5, before=message):
                author_name = msg.author.display_name
                # Jika asisten yang jawab, pakai nama bot atau identitasnya
                name = "Lu (Anak Moderator)" if msg.author.id == client.user.id else author_name
                history_lines.append(f"- {name}: {msg.content}")
            history_lines.reverse()
            
            history_text = "\n".join(history_lines) if history_lines else "Gak ada obrolan sebelumnya."

            prompt = message.content
            # Tambahkan instruksi khusus agar jawaban hanya 1 kalimat
            instruction = f"\n\n(Catatan: Jawab pesan ini hanya dalam 1 kalimat saja karena kamu sedang menanggapi mention ke Owner. Ini histori singkatnya:\n{history_text})"
            
            messages = [
                {"role": "system", "content": AI_PERSONALITY},
                {"role": "user", "content": f"{message.author.display_name}: {prompt}{instruction}"}
            ]

            async with message.channel.typing():
                reply = await ask_openrouter(messages)
                await message.reply(reply)
            return  # Berhenti di sini agar tidak memicu logika AI bot tag di bawah jika bot juga di-tag

        # Logika AI jika bot di-tag
        if client.user and client.user.mentioned_in(message):
            from commands.ai import ask_openrouter
            
            # Ambil riwayat pesan (misal 10 pesan terakhir sebelum pesan ini)
            history_lines = []
            async for msg in message.channel.history(limit=10, before=message):
                content = msg.content
                # Bersihkan tag bot dari history jika ada
                content = re.sub(r'<@!?%s>' % client.user.id, '', content).strip()
                if content:
                    author_name = msg.author.display_name
                    name = "Lu (Anak Moderator)" if msg.author.id == client.user.id else author_name
                    history_lines.append(f"- {name}: {content}")
            history_lines.reverse()
            
            history_context = "Histori obrolan sebelumnya:\n" + "\n".join(history_lines) if history_lines else ""

            # Bersihkan tag bot dari konten saat ini
            prompt = message.content
            prompt = re.sub(r'<@!?%s>' % client.user.id, '', prompt).strip()
            # Sertakan nama pengirim saat ini juga
            prompt_with_author = f"{message.author.display_name}: {prompt}" if prompt else "Halo"

            # Ambil konteks jika ada mention lain
            context_parts = []
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
                reply = await ask_openrouter(messages)
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