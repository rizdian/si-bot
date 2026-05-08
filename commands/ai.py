import logging

import aiohttp
import discord
from discord import app_commands

from config import GUILD_ID, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, AI_PERSONALITY

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)


async def ask_openrouter(messages: list) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_BASE_URL, headers=headers, json=payload) as resp:
            data = await resp.json()

            if resp.status != 200:
                error_msg = data.get("error", {}).get("message", "Unknown error")
                logger.error("OpenRouter API error: %s", error_msg)
                return f"❌ Gagal mendapatkan respons dari AI: {error_msg}"

            choices = data.get("choices", [])
            if not choices:
                return "❌ AI tidak memberikan respons."

            return choices[0]["message"]["content"]


def register_ai_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(name="chat", description="Tanya AI menggunakan OpenRouter", guild=TEST_GUILD)
    @app_commands.describe(prompt="Pertanyaan atau pesan untuk AI")
    async def chat(interaction: discord.Interaction, prompt: str) -> None:
        if not OPENROUTER_API_KEY:
            await interaction.response.send_message(
                "❌ API key OpenRouter belum dikonfigurasi.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            # Ambil riwayat pesan (misal 5 pesan terakhir)
            history = []
            async for msg in interaction.channel.history(limit=5):
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
            
            import re
            user_ids = re.findall(r"<@!?(\d+)>", prompt)
            
            for user_id in set(user_ids):
                member = interaction.guild.get_member(int(user_id))
                if not member:
                    try:
                        member = await interaction.guild.fetch_member(int(user_id))
                    except:
                        continue
                
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

            messages = [{"role": "system", "content": system_content}]
            messages.extend(history)
            
            # Tambahkan prompt terbaru jika belum masuk di history (interaction.channel.history mungkin belum mencatat slash command ini)
            # Karena /chat adalah slash command, pesannya belum ada di channel history saat diproses.
            messages.append({"role": "user", "content": prompt})

            reply = await ask_openrouter(messages)

            if len(reply) <= 4096:
                embed = discord.Embed(
                    title="🤖 AI Chat",
                    color=discord.Color.green(),
                )
                embed.add_field(name="💬 Pertanyaan", value=prompt[:1024], inline=False)
                embed.add_field(name="🧠 Jawaban", value=reply[:1024], inline=False)
                await interaction.followup.send(embed=embed)
            else:
                chunks = [reply[i:i + 4096] for i in range(0, len(reply), 4096)]
                embed = discord.Embed(
                    title="🤖 AI Chat",
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
