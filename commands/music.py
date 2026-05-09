import os
import asyncio
import logging
from typing import Optional

import discord
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from discord import app_commands

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, GUILD_ID

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)

COOKIE_PATH = "/app/cookies.txt"

# =========================
# yt-dlp Config
# =========================

COOKIE_PATH = "/app/cookies.txt"

ytdl_format_options = {
    "format": "bestaudio/best/bestaudio*",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "cookiefile": COOKIE_PATH,
}

ffmpeg_options = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn",
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# =========================
# Spotify Config
# =========================

sp: Optional[spotipy.Spotify] = None

if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
    try:
        sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
            )
        )
        logger.info("✅ Spotify initialized")
    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi Spotify: {e}")
else:
    logger.warning("⚠️ Spotify credentials not configured")


# =========================
# YTDL Source
# =========================

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume: float = 0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Unknown Title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url: str, *, loop=None, stream: bool = False):
        loop = loop or asyncio.get_event_loop()

        try:
            data = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(url, download=not stream),
            )
        except Exception as e:
            logger.error(f"❌ yt-dlp error: {e}")
            msg = str(e)

            if (
                "Sign in to confirm you’re not a bot" in msg
                or "Sign in to confirm you're not a bot" in msg
                or "YouTube memblokir permintaan ini" in msg
                or "not a bot" in msg.lower()
            ):
                raise Exception(
                    "YouTube memblokir bot karena terdeteksi sebagai bot. "
                    "Pastikan `cookies.txt` valid dan sudah ke-mount ke `/app/cookies.txt`."
                )

            if "403" in msg or "Forbidden" in msg:
                raise Exception(
                    "Kena Error 403 Forbidden. Coba export ulang `cookies.txt`, "
                    "restart container, atau update yt-dlp."
                )

            raise

        if not data:
            raise Exception("Data lagu kosong. YouTube/yt-dlp kagak ngasih hasil.")

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise Exception("Playlist/search result kosong.")
            data = entries[0]

        filename = data["url"] if stream else ytdl.prepare_filename(data)

        return cls(
            discord.FFmpegPCMAudio(filename, **ffmpeg_options),
            data=data,
        )


# =========================
# Music Player
# =========================

class MusicPlayer:
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.queue: asyncio.Queue[YTDLSource] = asyncio.Queue()
        self.next = asyncio.Event()
        self.current: Optional[YTDLSource] = None
        self.vc: Optional[discord.VoiceClient] = interaction.guild.voice_client

        interaction.client.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.interaction.client.wait_until_ready()

        while not self.interaction.client.is_closed():
            self.next.clear()

            try:
                source = await self.queue.get()
            except asyncio.CancelledError:
                break

            self.current = source

            if not self.vc or not self.vc.is_connected():
                self.current = None
                continue

            self.vc.play(
                source,
                after=lambda _: self.interaction.client.loop.call_soon_threadsafe(
                    self.next.set
                ),
            )

            await self.interaction.channel.send(
                f"🎶 **Sekarang diputar:** {source.title}"
            )

            await self.next.wait()

            source.cleanup()
            self.current = None

    async def destroy(self):
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()


players: dict[int, MusicPlayer] = {}


def get_player(interaction: discord.Interaction) -> MusicPlayer:
    guild_id = interaction.guild_id

    if guild_id not in players:
        players[guild_id] = MusicPlayer(interaction)

    player = players[guild_id]
    player.vc = interaction.guild.voice_client
    return player


# =========================
# Spotify Helper
# =========================

def spotify_to_query(url: str) -> tuple[str, Optional[str]]:
    if not sp:
        raise Exception("Fitur Spotify kagak dikonfigurasi sama mod-nya.")

    if "track" in url:
        track = sp.track(url)
        query = f"{track['name']} {track['artists'][0]['name']}"
        return query, None

    if "album" in url:
        album = sp.album(url)
        track = album["tracks"]["items"][0]
        query = f"{track['name']} {album['artists'][0]['name']}"
        info = f"ℹ️ Ini album ya? Gue puterin lagu pertamanya aja: **{track['name']}**"
        return query, info

    if "playlist" in url:
        playlist = sp.playlist(url)
        track = playlist["tracks"]["items"][0]["track"]
        query = f"{track['name']} {track['artists'][0]['name']}"
        info = f"ℹ️ Ini playlist ya? Gue puterin lagu pertamanya aja: **{track['name']}**"
        return query, info

    raise Exception("Link Spotify-nya kagak dikenali.")


# =========================
# Commands
# =========================

def register_music_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(
        name="play",
        description="Putar musik dari YouTube, Spotify, atau cari berdasarkan judul",
        guild=TEST_GUILD,
    )
    @app_commands.describe(search="URL YouTube/Spotify atau judul lagu")
    async def play(interaction: discord.Interaction, search: str):
        await interaction.response.defer()

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                "❌ Lu harus join voice channel dulu lah!"
            )

        try:
            voice_channel = interaction.user.voice.channel

            if not interaction.guild.voice_client:
                await voice_channel.connect(self_deaf=True, self_mute=False)
            elif interaction.guild.voice_client.channel != voice_channel:
                await interaction.guild.voice_client.move_to(voice_channel)
                await interaction.guild.voice_client.edit(deafen=True, mute=False)

            query = search

            if "spotify.com" in search:
                query, info_message = spotify_to_query(search)

                if info_message:
                    await interaction.followup.send(info_message)

            player = get_player(interaction)

            await interaction.followup.send(f"🔎 Nyari: **{query}**...")

            source = await YTDLSource.from_url(
                query,
                loop=client.loop,
                stream=True,
            )

            await player.queue.put(source)

            if player.current:
                await interaction.followup.send(
                    f"✅ Ditambahin ke antrean: **{source.title}**"
                )
            else:
                await interaction.followup.send(
                    f"✅ Dapet! Siap diputer: **{source.title}**"
                )

        except Exception as e:
            logger.error(f"Play error: {e}")
            await interaction.followup.send(f"❌ Error pas mau muter: {e}")

    @tree.command(
        name="skip",
        description="Lewatin lagu yang lagi diputar",
        guild=TEST_GUILD,
    )
    async def skip(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if not voice_client or not voice_client.is_playing():
            return await interaction.response.send_message(
                "❌ Kagak ada lagu yang lagi diputar, skip apaan?"
            )

        voice_client.stop()
        await interaction.response.send_message("⏭️ Oke, skip!")

    @tree.command(
        name="pause",
        description="Jeda musik yang lagi diputar",
        guild=TEST_GUILD,
    )
    async def pause(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if not voice_client or not voice_client.is_playing():
            return await interaction.response.send_message(
                "❌ Kagak ada lagu yang lagi diputar, mau nge-pause apaan?"
            )

        if voice_client.is_paused():
            return await interaction.response.send_message(
                "⚠️ Musiknya emang udah di-pause, gimana sih."
            )

        voice_client.pause()
        await interaction.response.send_message("⏸️ Oke, gue jeda dulu ya.")

    @tree.command(
        name="resume",
        description="Lanjutin musik yang lagi di-pause",
        guild=TEST_GUILD,
    )
    async def resume(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if not voice_client:
            return await interaction.response.send_message(
                "❌ Gue aja kagak ada di voice channel..."
            )

        if not voice_client.is_paused():
            return await interaction.response.send_message(
                "❌ Musiknya kagak lagi di-pause, kocak."
            )

        voice_client.resume()
        await interaction.response.send_message("▶️ Gas lagi!")

    @tree.command(
        name="stop",
        description="Berhentiin musik dan bot keluar dari voice channel",
        guild=TEST_GUILD,
    )
    async def stop(interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client

        if not voice_client:
            return await interaction.response.send_message(
                "❌ Gue aja kagak di voice channel..."
            )

        if interaction.guild_id in players:
            player = players.pop(interaction.guild_id)

            if player.vc and player.vc.is_playing():
                player.vc.stop()

        await voice_client.disconnect()
        await interaction.response.send_message("👋 Cabut dulu ya, mager.")

    @tree.command(
        name="queue",
        description="Lihat antrean lagu",
        guild=TEST_GUILD,
    )
    async def queue(interaction: discord.Interaction):
        if interaction.guild_id not in players:
            return await interaction.response.send_message(
                "📭 Antrean kosong, kayak hati lu."
            )

        player = players[interaction.guild_id]

        if player.queue.empty():
            return await interaction.response.send_message(
                "📭 Antrean kosong, kayak hati lu."
            )

        upcoming = list(player.queue._queue)
        fmt = "\n".join(
            f"{i + 1}. **{source.title}**"
            for i, source in enumerate(upcoming[:10])
        )

        embed = discord.Embed(
            title=f"Antrean di {interaction.guild.name}",
            description=fmt,
        )

        if len(upcoming) > 10:
            embed.set_footer(text=f"Dan {len(upcoming) - 10} lagu lainnya...")

        await interaction.response.send_message(embed=embed)