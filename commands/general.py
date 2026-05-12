from typing import Optional

import discord
from discord import app_commands

from config import GUILD_ID, OWNER_USER_ID
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

    @tree.command(name="avatar", description="Melihat avatar user", guild=TEST_GUILD)
    @app_commands.describe(member="Member yang ingin dilihat avatarnya (kosongkan untuk diri sendiri)")
    async def avatar(
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

        embed = discord.Embed(
            title=f"🖼️ Avatar {target.name}",
            color=target.color if target.color != discord.Color.default() else discord.Color.blue(),
            timestamp=now_utc(),
        )

        if target.avatar:
            embed.set_image(url=target.avatar.url)
            # Opsional: tambahkan link download atau link ke avatar
            # embed.description = f"[Link Avatar]({target.avatar.url})"
        else:
            embed.description = "User ini tidak memiliki avatar."

        await interaction.response.send_message(embed=embed)

    @tree.command(name="banner", description="Melihat banner user", guild=TEST_GUILD)
    @app_commands.describe(member="Member yang ingin dilihat bannernya (kosongkan untuk diri sendiri)")
    async def banner(
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
    ) -> None:
        target = member or interaction.user

        # Defer response as fetch_user is an API call
        await interaction.response.defer()

        try:
            # fetch_user to get the banner
            user = await client.fetch_user(target.id)
        except discord.HTTPException:
            await interaction.followup.send("❌ Gagal mengambil data user.")
            return

        embed = discord.Embed(
            title=f"🖼️ Banner {user.name}",
            color=target.color if isinstance(target, discord.Member) and target.color != discord.Color.default() else discord.Color.blue(),
            timestamp=now_utc(),
        )

        if user.banner:
            embed.set_image(url=user.banner.url)
        else:
            embed.description = "User ini tidak memiliki banner."

        await interaction.followup.send(embed=embed)

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
        if interaction.user.id != OWNER_USER_ID:
            await interaction.response.send_message(
                "❌ Kamu bukan owner.",
                ephemeral=True,
            )
            return

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
        # pastikan di server
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Command ini hanya bisa dipakai di server.",
                ephemeral=True
            )
            return

        member = interaction.user

        # pastikan user adalah member & ada di voice
        if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
            await interaction.response.send_message(
                "❌ Kamu harus berada di voice channel!",
                ephemeral=True
            )
            return

        channel = member.voice.channel

        try:
            vc = interaction.guild.voice_client

            # kalau sudah connect → pindah channel
            if vc and vc.is_connected():
                await vc.move_to(channel)
                await vc.edit(deafen=True, mute=False)
            else:
                # connect + langsung deaf, pastikan kaga mute
                vc = await channel.connect(self_deaf=True, self_mute=False)

            await interaction.response.send_message(
                f"🔊 Join ke **{channel.name}** (Deafened & Unmuted)",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Gagal join voice: {e}",
                ephemeral=True
            )

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

    # @tree.command(name="sync", description="Sync command bot (Owner Only)", guild=TEST_GUILD)
    # @app_commands.describe(scope="Scope untuk sync (global/guild)")
    # async def sync(interaction: discord.Interaction, scope: Optional[str] = "guild") -> None:
    #     if interaction.user.id != OWNER_USER_ID:
    #         await interaction.response.send_message(
    #             "❌ Lu bukan owner gue, jangan sok asik dah.",
    #             ephemeral=True
    #         )
    #         return
    #
    #     await interaction.response.defer(ephemeral=True)
    #
    #     try:
    #         if scope == "global":
    #             synced = await tree.sync()
    #             await interaction.followup.send(f"✅ Berhasil sync {len(synced)} command secara global.")
    #         else:
    #             guild = interaction.guild
    #             if guild:
    #                 tree.copy_global_to(guild=guild)
    #                 synced = await tree.sync(guild=guild)
    #                 await interaction.followup.send(f"✅ Berhasil sync {len(synced)} command ke guild ini.")
    #             else:
    #                 await interaction.followup.send("❌ Guild kagak ketemu njir.")
    #     except Exception as e:
    #         await interaction.followup.send(f"❌ Gagal sync: {e}")