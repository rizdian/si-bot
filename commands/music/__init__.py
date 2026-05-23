import logging
from typing import Optional

import discord
from discord import app_commands

from config import GUILD_ID, OWNER_USER_ID

from .source import YTDLSource
from .player import MusicPlayer, players
from .play import do_play
from .lyrics import fetch_lyrics, extract_artist_title, send_lyrics
from .embeds import error_embed, success_embed, info_embed, warning_embed

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)


def register_music_commands(tree: app_commands.CommandTree, client: discord.Client):

    @tree.command(
        name="play",
        description="Putar musik dari YouTube, Spotify, atau cari berdasarkan judul",
        guild=TEST_GUILD,
    )
    @app_commands.describe(search="URL YouTube/Spotify atau judul lagu")
    async def play(interaction: discord.Interaction, search: str):
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return await interaction.channel.send(
                embed=error_embed("Interaksi expired, coba lagi.")
            )

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                embed=error_embed("Kamu harus join voice channel dulu!")
            )

        try:
            await do_play(
                search=search,
                guild=interaction.guild,
                voice_channel=interaction.user.voice.channel,
                send=interaction.followup.send,
                channel=interaction.channel,
                requester=interaction.user,
                client=client,
            )
        except Exception as e:
            logger.error("Play error: %s", e)
            await interaction.followup.send(embed=error_embed(f"Error: {e}"))

    @tree.command(name="skip", description="Lewati lagu yang sedang diputar", guild=TEST_GUILD)
    async def skip(interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada lagu yang diputar.")
            )
        vc.stop()
        await interaction.response.send_message(
            embed=success_embed("⏭️ Lagu diskip!")
        )

    @tree.command(name="pause", description="Jeda musik yang sedang diputar", guild=TEST_GUILD)
    async def pause(interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada lagu yang diputar.")
            )
        if vc.is_paused():
            return await interaction.response.send_message(
                embed=warning_embed("Musik sudah di-pause.")
            )
        vc.pause()
        await interaction.response.send_message(
            embed=success_embed("⏸️ Musik dijeda.")
        )

    @tree.command(name="resume", description="Lanjutkan musik yang di-pause", guild=TEST_GUILD)
    async def resume(interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(
                embed=error_embed("Bot tidak ada di voice channel.")
            )
        if not vc.is_paused():
            return await interaction.response.send_message(
                embed=error_embed("Musik tidak di-pause.")
            )
        vc.resume()
        await interaction.response.send_message(
            embed=success_embed("▶️ Musik dilanjutkan!")
        )

    @tree.command(
        name="stop",
        description="Hentikan musik dan bot keluar dari voice channel",
        guild=TEST_GUILD,
    )
    async def stop(interaction: discord.Interaction):
        if interaction.user.id != OWNER_USER_ID:
            return await interaction.response.send_message(
                embed=error_embed("❌ Kamu bukan owner."), ephemeral=True
            )

        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(
                embed=error_embed("Bot tidak ada di voice channel.")
            )

        if interaction.guild_id in players:
            player = players.pop(interaction.guild_id)
            player.autoplay = False
            player._cancel_prefetch()
            if player.vc and player.vc.is_playing():
                player.vc.stop()

        await vc.disconnect()
        await interaction.response.send_message(
            embed=success_embed("👋 Bot keluar dari voice channel.")
        )

    @tree.command(name="queue", description="Lihat antrean lagu", guild=TEST_GUILD)
    async def queue(interaction: discord.Interaction):
        if interaction.guild_id not in players:
            return await interaction.response.send_message(
                embed=warning_embed("📭 Antrean kosong.")
            )

        player = players[interaction.guild_id]
        if player.queue.empty() and not player.current:
            return await interaction.response.send_message(
                embed=warning_embed("📭 Antrean kosong.")
            )

        upcoming = list(player.queue._queue.copy())
        lines = []
        if player.current:
            lines.append(f"**Sedang diputar:** {player.current.title}\n")
        if upcoming:
            lines.append("**Antrean:**\n" + "\n".join(
                f"{i + 1}. **{s.title}**" for i, s in enumerate(upcoming[:10])
            ))
            if len(upcoming) > 10:
                lines.append(f"\n...dan {len(upcoming) - 10} lagu lainnya.")

        embed = discord.Embed(title="Antrean Lagu", description="\n".join(lines), color=discord.Color.blurple())
        if player.loop_mode != MusicPlayer.LOOP_OFF:
            loop_labels = {
                MusicPlayer.LOOP_TRACK: "🔂 Track Loop",
                MusicPlayer.LOOP_QUEUE: "🔁 Queue Loop",
            }
            embed.set_footer(text=loop_labels.get(player.loop_mode, ""))

        await interaction.response.send_message(embed=embed)

    @tree.command(name="loop", description="Atur mode pengulangan", guild=TEST_GUILD)
    @app_commands.describe(mode="Pilih mode loop")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Off", value="off"),
        app_commands.Choice(name="Track (ulang 1 lagu)", value="track"),
        app_commands.Choice(name="Queue (ulang semua)", value="queue"),
    ])
    async def loop_cmd(interaction: discord.Interaction, mode: str):
        if interaction.guild_id not in players:
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada player aktif. Putar lagu dulu.")
            )

        player = players[interaction.guild_id]
        if mode not in (MusicPlayer.LOOP_OFF, MusicPlayer.LOOP_TRACK, MusicPlayer.LOOP_QUEUE):
            return await interaction.response.send_message(
                embed=error_embed("Mode tidak valid.")
            )

        player.loop_mode = mode
        if mode == MusicPlayer.LOOP_OFF:
            player._played_sources.clear()

        labels = {
            MusicPlayer.LOOP_OFF: ("⏹️", "Loop dimatikan"),
            MusicPlayer.LOOP_TRACK: ("🔂", "Loop track aktif — lagu akan diulang"),
            MusicPlayer.LOOP_QUEUE: ("🔁", "Loop queue aktif — semua lagu akan diulang"),
        }
        emoji, text = labels[mode]
        await interaction.response.send_message(
            embed=success_embed(f"{emoji} {text}")
        )

    @tree.command(
        name="autoplay",
        description="Nyalakan/matikan autoplay (otomatis putar lagu terkait)",
        guild=TEST_GUILD,
    )
    @app_commands.describe(mode="Nyalakan atau matikan autoplay")
    @app_commands.choices(mode=[
        app_commands.Choice(name="On", value="on"),
        app_commands.Choice(name="Off", value="off"),
    ])
    async def autoplay_cmd(interaction: discord.Interaction, mode: str):
        if interaction.guild_id not in players:
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada player aktif. Putar lagu dulu.")
            )

        player = players[interaction.guild_id]
        player.autoplay = mode == "on"

        if player.autoplay:
            await interaction.response.send_message(
                embed=success_embed("🔀 Autoplay **aktif** — lagu terkait akan diputar otomatis saat queue kosong.")
            )
        else:
            await interaction.response.send_message(
                embed=success_embed("🔀 Autoplay **dimatikan**.")
            )

    @tree.command(name="lyrics", description="Cari lirik lagu", guild=TEST_GUILD)
    @app_commands.describe(
        artist="Nama artis (opsional jika sedang memutar lagu)",
        title="Judul lagu (opsional jika sedang memutar lagu)",
    )
    async def lyrics(
        interaction: discord.Interaction,
        artist: Optional[str] = None,
        title: Optional[str] = None,
    ):
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return await interaction.channel.send(
                embed=error_embed("Interaksi expired, coba lagi.")
            )

        if not artist and not title:
            player = players.get(interaction.guild_id)
            artist, title = extract_artist_title(player)
            if not artist and not title:
                return await interaction.followup.send(
                    embed=error_embed("Tidak ada lagu yang diputar, dan tidak ada judul diberikan.")
                )

        query_display = f"{artist} - {title}" if artist else title
        await interaction.followup.send(
            embed=info_embed(f"🔎 Mencari lirik: **{query_display}**...")
        )

        lyrics_text = await fetch_lyrics(artist or "", title or "")
        if not lyrics_text:
            return await interaction.followup.send(
                embed=error_embed(f"Lirik untuk **{query_display}** tidak ditemukan.")
            )

        await send_lyrics(interaction.followup.send, query_display, lyrics_text)
