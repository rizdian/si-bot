import logging

import aiohttp
import discord
from discord import app_commands

from config import GUILD_ID, OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL, AI_PERSONALITY

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)


async def ask_openrouter(prompt: str, context: str = None) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    system_content = AI_PERSONALITY
    if context:
        system_content += f"\n\nKonteks tambahan tentang member yang di-mention:\n{context}"
        
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ],
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
            # Deteksi member yang di-mention
            mentions = interaction.message.mentions if interaction.message else []
            # Namun pada slash command, interaction.message biasanya None.
            # Kita perlu mengekstrak dari prompt atau menggunakan app_commands.User jika ingin lebih eksplisit.
            # Tapi user ingin "kalo tag member", jadi kita asumsikan lewat string prompt.
            
            context_parts = []
            
            # Cari mention format <@ID> atau <@!ID> dalam prompt
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

            context = "\n".join(context_parts) if context_parts else None
            reply = await ask_openrouter(prompt, context)

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
