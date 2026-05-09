import logging
import re
import asyncio

import aiohttp
import discord
from discord import app_commands

from config import GUILD_ID, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, AI_PERSONALITY

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)


async def ask_openrouter(session: aiohttp.ClientSession, messages: list) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    max_retries = 3
    retry_delay = 2

    # Semaphore untuk membatasi request simultan agar tidak membanjiri API
    if not hasattr(session, '_openrouter_sem'):
        session._openrouter_sem = asyncio.Semaphore(2)

    async with session._openrouter_sem:
        for attempt in range(max_retries):
            try:
                async with session.post(OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=20) as resp:
                    if resp.status == 429:
                        if attempt < max_retries - 1:
                            logger.warning(f"⚠️ Rate limited (429) oleh OpenRouter. Retrying in {retry_delay}s... (Attempt {attempt + 1})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                            continue
                        else:
                            return "❌ Waduh, Aku lagi sibuk banget . Coba lagi entar ya."

                    data = await resp.json()

                    if resp.status != 200:
                        error_msg = data.get("error", {}).get("message", "Unknown error")
                        logger.error("OpenRouter API error: %s", error_msg)
                        return f"❌ Bentar Lagi Lag coba Tag Moderator"

                    choices = data.get("choices", [])
                    if not choices:
                        return "❌ Bengong."

                    return choices[0]["message"]["content"]
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"⚠️ Error pas konek ke OpenRouter: {e}. Retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.exception("Error fatal saat menghubungi OpenRouter")
                    return f"❌ Bentar Lagi Lag coba Tag Moderator."
    
    return "❌ Bentar Lagi Lag coba Tag Moderator."


# Cooldown storage
ai_cooldowns = {}

def register_ai_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(name="chat", description="Tanya Langit menggunakan OpenRouter", guild=TEST_GUILD)
    @app_commands.describe(prompt="Pertanyaan atau pesan untuk Langit")
    async def chat(interaction: discord.Interaction, prompt: str) -> None:
        if not OPENROUTER_API_KEY:
            await interaction.response.send_message(
                "❌ API key OpenRouter belum dikonfigurasi.",
                ephemeral=True,
            )
            return

        # Cooldown check
        user_id = interaction.user.id
        now = asyncio.get_event_loop().time()
        if user_id in ai_cooldowns and now - ai_cooldowns[user_id] < 10:
            retry_after = int(10 - (now - ai_cooldowns[user_id]))
            await interaction.response.send_message(
                f"⚠️ Santai dikit napa, tunggu {retry_after} detik lagi baru nanya lagi.",
                ephemeral=True
            )
            return

        ai_cooldowns[user_id] = now

        await interaction.response.defer(thinking=True)

        try:
            # Ambil riwayat pesan (misal 5 pesan terakhir) secara paralel
            history = []
            history_tasks = []
            async for msg in interaction.channel.history(limit=5):
                history_tasks.append(msg)
            
            for msg in history_tasks:
                if msg.author.bot:
                    if msg.author.id == client.user.id:
                        # Jika pesan bot memiliki embed (hasil /chat sebelumnya), ambil isinya
                        if msg.embeds:
                            for embed in msg.embeds:
                                for field in embed.fields:
                                    if field.name == "🧠 Jawaban":
                                        history.append({"role": "assistant", "content": field.value})
                        else:
                            history.append({"role": "assistant", "content": msg.content})
                else:
                    # Bersihkan prompt jika ada tag bot (biasanya tidak ada di slash command tapi untuk jaga-jaga)
                    content = msg.content
                    history.append({"role": "user", "content": content})
            
            # Balik urutan agar kronologis (lama ke baru)
            history.reverse()

            context_parts = []
            # Tambahkan info tentang pengirim pesan saat ini
            context_parts.append(f"- {interaction.user.display_name} (ID: {interaction.user.id}) adalah pengirim pesan saat ini.")
            
            user_ids = re.findall(r"<@!?(\d+)>", prompt)
            
            mention_tasks = []
            for user_id in set(user_ids):
                user_id_int = int(user_id)
                member = interaction.guild.get_member(user_id_int)
                if not member:
                    mention_tasks.append(interaction.guild.fetch_member(user_id_int))
                else:
                    mention_tasks.append(asyncio.sleep(0, result=member))

            if mention_tasks:
                members = await asyncio.gather(*mention_tasks, return_exceptions=True)
                for member in members:
                    if isinstance(member, discord.Member):
                        roles = [role.name.lower() for role in member.roles]
                        category = "umum"
                        if any("mod" in r for r in roles) or any("admin" in r for r in roles):
                            category = "moderator"
                        elif any("boy" in r for r in roles):
                            category = "boys"
                        elif any("girl" in r for r in roles):
                            category = "girls"
                        
                        context_parts.append(f"- {member.display_name} (ID: {member.id}) adalah seorang {category}.")

            system_content = AI_PERSONALITY
            if context_parts:
                context = "\n".join(context_parts)
                system_content += f"\n\nKonteks tambahan tentang member yang di-mention:\n{context}"

            messages = [{"role": "system", "content": system_content}]
            messages.extend(history)
            
            # Tambahkan prompt terbaru jika belum masuk di history (interaction.channel.history mungkin belum mencatat slash command ini)
            # Karena /chat adalah slash command, pesannya belum ada di channel history saat diproses.
            messages.append({"role": "user", "content": prompt})

            reply = await ask_openrouter(client.ai_session, messages)

            if len(reply) <= 4096:
                embed = discord.Embed(
                    title="🤖 Langit Chat",
                    color=discord.Color.green(),
                )
                embed.add_field(name="💬 Pertanyaan", value=prompt[:1024], inline=False)
                embed.add_field(name="🧠 Jawaban", value=reply[:1024], inline=False)
                await interaction.followup.send(embed=embed)
            else:
                chunks = [reply[i:i + 4096] for i in range(0, len(reply), 4096)]
                embed = discord.Embed(
                    title="🤖 Langit Chat",
                    description=chunks[0],
                    color=discord.Color.green(),
                )
                embed.add_field(name="💬 Pertanyaan", value=prompt[:1024], inline=False)
                await interaction.followup.send(embed=embed)

                for chunk in chunks[1:]:
                    await interaction.followup.send(content=chunk)

        except Exception as e:
            logger.exception("Error saat menghubungi OpenRouter")
            await interaction.followup.send(
                f"❌ Terjadi kesalahan: {e}",
                ephemeral=True,
            )
