from typing import Optional

import discord
from discord import app_commands

from config import GUILD_ID
from utils.logger import send_log_embed, format_datetime, now_utc


TEST_GUILD = discord.Object(id=GUILD_ID)


def register_general_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(name="ping", description="Cek bot hidup", guild=TEST_GUILD)
    async def ping(interaction: discord.Interaction) -> None:
        latency = round(client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! ({latency}ms)")

    @tree.command(name="serverinfo", description="Melihat informasi server", guild=TEST_GUILD)
    async def serverinfo(interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "❌ Command ini hanya bisa digunakan di server!",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🏰 {guild.name}",
            color=discord.Color.blue(),
            timestamp=now_utc(),
        )
        embed.add_field(name="🆔 ID Server", value=str(guild.id), inline=True)
        embed.add_field(name="👑 Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="👥 Members", value=str(guild.member_count), inline=True)
        embed.add_field(
            name="📅 Created At",
            value=format_datetime(guild.created_at),
            inline=True,
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await interaction.response.send_message(embed=embed)

    @tree.command(name="userinfo", description="Melihat informasi user", guild=TEST_GUILD)
    @app_commands.describe(member="Member yang ingin dilihat (kosongkan untuk diri sendiri)")
    async def userinfo(
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
    ) -> None:
        target = member or interaction.user

        if not isinstance(target, discord.Member):
            await interaction.response.send_message(
                "❌ Gagal mengambil data member.",
                ephemeral=True,
            )
            return

        roles = ", ".join(role.mention for role in target.roles[1:]) or "No roles"

        embed = discord.Embed(
            title=f"👤 {target.name}",
            color=target.color if target.color != discord.Color.default() else discord.Color.blue(),
            timestamp=now_utc(),
        )
        embed.add_field(name="🆔 ID", value=str(target.id), inline=True)
        embed.add_field(name="📅 Joined At", value=format_datetime(target.joined_at), inline=True)
        embed.add_field(name="📅 Created At", value=format_datetime(target.created_at), inline=True)
        embed.add_field(name="🏷 Roles", value=roles, inline=False)

        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)

        await interaction.response.send_message(embed=embed)

    @tree.command(name="log", description="Test log manual", guild=TEST_GUILD)
    async def log(interaction: discord.Interaction) -> None:
        await send_log_embed(
            client=client,
            title="📡 TRACE LOG",
            color=discord.Color.green(),
            fields=[
                ("👤 User", interaction.user.mention, False),
                ("📌 Event", "Manual Trigger", False),
            ],
        )

        await interaction.response.send_message(
            "✅ Log sent to log channel!",
            ephemeral=True,
        )

    @tree.command(name="say", description="Bot akan mengatakan sesuatu", guild=TEST_GUILD)
    @app_commands.describe(
        message="Pesan yang ingin dikirim",
        user="Optional: mention user",
    )
    async def say(
        interaction: discord.Interaction,
        message: str,
        user: Optional[discord.Member] = None,
    ) -> None:
        content = f"{user.mention} {message}" if user else message

        embed = discord.Embed(
            description=content,
            color=discord.Color.purple(),
        )

        if interaction.channel is None:
            await interaction.response.send_message(
                "❌ Channel tidak ditemukan.",
                ephemeral=True,
            )
            return

        await interaction.channel.send(embed=embed)

        await interaction.response.send_message(
            "✅ Pesan berhasil dikirim!",
            ephemeral=True,
        )

    @tree.command(name="join", description="Bot join ke voice channel kamu", guild=TEST_GUILD)
    async def join(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("join command loaded", ephemeral=True)

    @tree.command(name="leave", description="Bot keluar dari voice channel", guild=TEST_GUILD)
    async def leave(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Command ini hanya bisa dipakai di server.",
                ephemeral=True,
            )
            return

        vc = interaction.guild.voice_client

        if not vc:
            await interaction.response.send_message(
                "❌ Bot tidak ada di voice channel!",
                ephemeral=True,
            )
            return

        await vc.disconnect()

        await interaction.response.send_message(
            "👋 Keluar dari voice channel",
            ephemeral=True,
        )