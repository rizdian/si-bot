import os
import asyncio
import discord
import yt_dlp
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from discord import app_commands
from typing import Optional
import logging
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, GUILD_ID

logger = logging.getLogger("bot")

TEST_GUILD = discord.Object(id=GUILD_ID)

# Konfigurasi yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
}

# Load cookies if available to avoid bot detection
if os.path.exists('cookies.txt'):
    if os.path.isfile('cookies.txt'):
        ytdl_format_options['cookiefile'] = 'cookies.txt'
        logger.info("🍪 Cookies loaded from cookies.txt")
    else:
        logger.error("❌ 'cookies.txt' ditemukan tetapi berupa FOLDER, bukan FILE. Harap hapus folder tersebut di server host.")
else:
    logger.warning("⚠️ cookies.txt not found. YouTube might block requests.")

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# Inisialisasi Spotify
sp = None
if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        ))
    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi Spotify: {e}")

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            logger.error(f"❌ yt-dlp error: {e}")
            msg = str(e)
            if "Sign in to confirm you’re not a bot" in msg or "YouTube memblokir permintaan ini" in msg:
                raise Exception("YouTube memblokir bot karena terdeteksi sebagai bot. **WAJIB: Tambahkan file `cookies.txt` yang valid ke folder bot.** Lihat cara ekspor cookies di browser lu.")
            elif "403" in msg:
                raise Exception("Kena Error 403 (Forbidden). YouTube kayaknya nolak akses. Coba update `cookies.txt` atau tunggu sebentar.")
            raise e

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicPlayer:
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.current = None
        self.vc = interaction.guild.voice_client
        
        interaction.client.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.interaction.client.wait_until_ready()

        while not self.interaction.client.is_closed():
            self.next.clear()

            # Tunggu lagu berikutnya. Tanpa timeout agar bot tetap di room 24/7.
            source = await self.queue.get()

            self.current = source
            self.vc.play(source, after=lambda _: self.interaction.client.loop.call_soon_threadsafe(self.next.set))
            
            await self.interaction.channel.send(f'🎶 **Sekarang diputar:** {source.title}')
            await self.next.wait()

            # Make sure the FFmpeg process is cleaned up.
            source.cleanup()
            self.current = None

    def destroy(self):
        return self.interaction.client.loop.create_task(self.vc.disconnect())

players = {}

def get_player(interaction: discord.Interaction):
    if interaction.guild_id not in players:
        players[interaction.guild_id] = MusicPlayer(interaction)
    return players[interaction.guild_id]

def register_music_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(name="play", description="Putar musik dari YouTube, Spotify, atau cari berdasarkan judul", guild=TEST_GUILD)
    @app_commands.describe(search="URL YouTube/Spotify atau judul lagu")
    async def play(interaction: discord.Interaction, search: str):
        await interaction.response.defer()

        # Pastikan user di voice channel
        if not interaction.user.voice:
            return await interaction.followup.send("❌ Lu harus join voice channel dulu lah!")

        # Join voice channel jika belum
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect(self_deaf=True, self_mute=False)
        elif interaction.guild.voice_client.channel != interaction.user.voice.channel:
            await interaction.guild.voice_client.move_to(interaction.user.voice.channel)
            await interaction.guild.voice_client.edit(deafen=True, mute=False)

        query = search
        # Handle Spotify links
        if "spotify.com" in search:
            if not sp:
                return await interaction.followup.send("❌ Fitur Spotify kagak dikonfigurasi sama mod-nya.")
            
            try:
                if "track" in search:
                    track = sp.track(search)
                    query = f"{track['name']} {track['artists'][0]['name']}"
                elif "album" in search:
                    # Ambil lagu pertama dari album untuk simplifikasi (atau handle playlist/album kedepannya)
                    album = sp.album(search)
                    track = album['tracks']['items'][0]
                    query = f"{track['name']} {album['artists'][0]['name']}"
                    await interaction.followup.send(f"ℹ️ Ini album ya? Gue puterin lagu pertamanya aja: **{track['name']}**")
                elif "playlist" in search:
                    playlist = sp.playlist(search)
                    track = playlist['tracks']['items'][0]['track']
                    query = f"{track['name']} {track['artists'][0]['name']}"
                    await interaction.followup.send(f"ℹ️ Ini playlist ya? Gue puterin lagu pertamanya aja: **{track['name']}**")
            except Exception as e:
                logger.error(f"Spotify error: {e}")
                return await interaction.followup.send("❌ Error pas nyoba baca link Spotify lu.")

        try:
            player = get_player(interaction)
            source = await YTDLSource.from_url(query, loop=client.loop, stream=True)
            await player.queue.put(source)
            
            if player.current:
                await interaction.followup.send(f"✅ Ditambahin ke antrean: **{source.title}**")
            else:
                await interaction.followup.send(f"🔎 Nyari: **{query}**... dapet!")
        except Exception as e:
            logger.error(f"Play error: {e}")
            await interaction.followup.send(f"❌ Error pas mau muter: {e}")

    @tree.command(name="skip", description="Lewatin lagu yang lagi diputar", guild=TEST_GUILD)
    async def skip(interaction: discord.Interaction):
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
            return await interaction.response.send_message("❌ Kagak ada lagu yang lagi diputar, skip apaan?")
        
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Oke, skip!")

    @tree.command(name="pause", description="Jeda musik yang lagi diputar", guild=TEST_GUILD)
    async def pause(interaction: discord.Interaction):
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
            return await interaction.response.send_message("❌ Kagak ada lagu yang lagi diputar, mau nge-pause apaan?")
        
        if interaction.guild.voice_client.is_paused():
            return await interaction.response.send_message("⚠️ Musiknya emang udah di-pause, gimana sih.")

        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸️ Oke, gue jeda dulu ya.")

    @tree.command(name="resume", description="Lanjutin musik yang lagi di-pause", guild=TEST_GUILD)
    async def resume(interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            return await interaction.response.send_message("❌ Gue aja kagak ada di voice channel...")

        if not interaction.guild.voice_client.is_paused():
            return await interaction.response.send_message("❌ Musiknya kagak lagi di-pause, kocak.")

        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶️ Gas lagi!")

    @tree.command(name="stop", description="Berhentiin musik dan bot keluar dari voice channel", guild=TEST_GUILD)
    async def stop(interaction: discord.Interaction):
        if not interaction.guild.voice_client:
            return await interaction.response.send_message("❌ Gue aja kagak di voice channel...")

        if interaction.guild_id in players:
            # Kita gak perlu panggil destroy manual karena disconnect akan memicu cleanup di loop jika kita handle dengan benar
            # Tapi untuk aman, hapus dari dict
            players[interaction.guild_id].vc.stop()
            del players[interaction.guild_id]

        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("👋 Cabut dulu ya, mager.")

    @tree.command(name="queue", description="Lihat antrean lagu", guild=TEST_GUILD)
    async def queue(interaction: discord.Interaction):
        if interaction.guild_id not in players or players[interaction.guild_id].queue.empty():
            return await interaction.response.send_message("📭 Antrean kosong, kayak hati lu.")

        player = players[interaction.guild_id]
        upcoming = list(player.queue._queue)
        fmt = '\n'.join(f'{i+1}. **{s.title}**' for i, s in enumerate(upcoming[:10]))
        
        embed = discord.Embed(title=f"Antrean di {interaction.guild.name}", description=fmt)
        if len(upcoming) > 10:
            embed.set_footer(text=f"Dan {len(upcoming) - 10} lagu lainnya...")
            
        await interaction.response.send_message(embed=embed)
