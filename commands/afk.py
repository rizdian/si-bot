from typing import Optional

import discord
from discord import app_commands

from config import GUILD_ID
from utils.afk import set_afk, get_all_afk, format_duration, is_afk
from utils.logger import now_utc

TEST_GUILD = discord.Object(id=GUILD_ID)

AFK_PREFIX = "[AFK]"


def _strip_afk_prefix(name: str) -> str:
    if name.startswith(AFK_PREFIX):
        return name[len(AFK_PREFIX):].strip()
    return name


def register_afk_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(name="afk", description="Set status AFK", guild=TEST_GUILD)
    @app_commands.describe(reason="Alasan AFK (opsional)")
    async def afk(interaction: discord.Interaction, reason: Optional[str] = None) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Command ini hanya bisa digunakan di server.",
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Command ini hanya bisa digunakan di server.",
                ephemeral=True,
            )
            return

        if is_afk(member.id):
            await interaction.response.send_message(
                "❌ Lu udah AFK belom tadi, santuy.",
                ephemeral=True,
            )
            return

        current_nick = member.nick if member.nick else member.global_name or member.name
        original_nick = _strip_afk_prefix(current_nick)
        new_nick = f"{AFK_PREFIX} {original_nick}"

        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Gue gak bisa ganti nickname lu. Cek permission bot.",
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.response.send_message(
                "❌ Gagal ganti nickname.",
                ephemeral=True,
            )
            return

        set_afk(member.id, original_nick, reason)

        msg = f"💤 {member.mention} sekarang AFK!"
        if reason:
            msg += f" Alasan: {reason}"

        await interaction.response.send_message(msg)

    @tree.command(name="afklist", description="Lihat daftar member yang lagi AFK", guild=TEST_GUILD)
    async def afklist(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Command ini hanya bisa digunakan di server.",
                ephemeral=True,
            )
            return

        all_afk = get_all_afk()

        if not all_afk:
            await interaction.response.send_message("✅ Semua member online, gak ada yang AFK.")
            return

        embed = discord.Embed(
            title="💤 AFK List",
            color=discord.Color.orange(),
            timestamp=now_utc(),
        )

        lines = []
        for user_id, data in all_afk.items():
            member = interaction.guild.get_member(user_id)
            if member is None:
                continue

            duration = format_duration(data["timestamp"])
            reason = data.get("reason")
            line = f"**{member.display_name}** — {duration}"
            if reason:
                line += f"\n  ↳ *{reason}*"
            lines.append(line)

        if not lines:
            await interaction.response.send_message("✅ Semua member online, gak ada yang AFK.")
            return

        description = "\n\n".join(lines)
        embed.description = description

        await interaction.response.send_message(embed=embed)
