import os
import asyncio
import logging
from typing import Optional
from urllib.parse import quote

import aiohttp
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

ytdl_format_options = {
    "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",

    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": "/app/data/cookies.txt",

    # JS runtime for youtube anti-bot
    "js_runtimes": {
        "node": {}
    },

    # EJS challenge solver
    "remote_components": ["ejs:github"],

    # safest client currently
    "extractor_args": {
        "youtube": {
            "player_client": ["web_creator", "android_vr", "web"],
        }
    },

    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Referer": "https://www.youtube.com/",
    },
}


_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

ffmpeg_options = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
        f"-headers 'User-Agent: {_UA}\r\nReferer: https://www.youtube.com/\r\n'"
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
    async def create_source(cls, data, *, stream: bool = False):
        if not data:
            raise Exception("Data lagu kosong.")

        logger.debug(
            f"[yt-dlp] create_source called | "
            f"title={data.get('title')!r} "
            f"stream={stream}"
        )

        if stream:
            audio_url = None

            requested_formats = data.get("requested_formats", [])
            formats = data.get("formats", [])
            headers = data.get("http_headers", {})

            logger.debug(
                f"[yt-dlp] requested_formats={len(requested_formats)} "
                f"formats={len(formats)}"
            )

            logger.debug(
                f"[yt-dlp] HTTP_HEADERS = {headers}"
            )

            # =========================
            # PRIORITY 1
            # requested_formats
            # =========================
            if requested_formats:
                logger.debug("[yt-dlp] Trying requested_formats...")

                for idx, fmt in enumerate(requested_formats):
                    logger.debug(
                        f"[yt-dlp] requested_format[{idx}] | "
                        f"itag={fmt.get('format_id')} "
                        f"ext={fmt.get('ext')} "
                        f"abr={fmt.get('abr')} "
                        f"acodec={fmt.get('acodec')} "
                        f"vcodec={fmt.get('vcodec')}"
                    )

                    if fmt.get("acodec") != "none":
                        audio_url = fmt.get("url")

                        logger.debug(
                            f"[yt-dlp] Selected requested_format | "
                            f"itag={fmt.get('format_id')} "
                            f"url={audio_url}"
                        )
                        break

            # =========================
            # PRIORITY 2
            # formats audio detection
            # =========================
            if not audio_url:
                logger.debug("[yt-dlp] Trying formats audio detection...")

                audio_formats = []

                for fmt in formats:
                    logger.debug(
                        f"[yt-dlp] format | "
                        f"itag={fmt.get('format_id')} "
                        f"ext={fmt.get('ext')} "
                        f"abr={fmt.get('abr')} "
                        f"acodec={fmt.get('acodec')} "
                        f"vcodec={fmt.get('vcodec')}"
                    )

                    if fmt.get("acodec") != "none":
                        audio_formats.append(fmt)

                logger.debug(
                    f"[yt-dlp] audio_formats_found={len(audio_formats)}"
                )

                # prioritaskan audio-only
                audio_only = [
                    f for f in audio_formats
                    if f.get("vcodec") == "none"
                ]

                logger.debug(
                    f"[yt-dlp] audio_only_found={len(audio_only)}"
                )

                selected = None

                if audio_only:
                    selected = max(
                        audio_only,
                        key=lambda f: f.get("abr") or 0
                    )

                    logger.debug(
                        "[yt-dlp] Using audio-only stream"
                    )

                elif audio_formats:
                    selected = max(
                        audio_formats,
                        key=lambda f: f.get("abr") or 0
                    )

                    logger.warning(
                        "[yt-dlp] No audio-only stream found. "
                        "Fallback to progressive stream."
                    )

                if selected:
                    audio_url = selected.get("url")

                    logger.debug(
                        f"[yt-dlp] Selected stream | "
                        f"itag={selected.get('format_id')} "
                        f"ext={selected.get('ext')} "
                        f"abr={selected.get('abr')} "
                        f"acodec={selected.get('acodec')} "
                        f"vcodec={selected.get('vcodec')} "
                        f"url={audio_url}"
                    )

            # =========================
            # PRIORITY 3
            # fallback
            # =========================
            if not audio_url:
                logger.warning(
                    "[yt-dlp] No stream found. "
                    "Fallback to data['url']"
                )

                audio_url = data.get("url")

            if not audio_url:
                logger.error("[yt-dlp] FINAL FAIL | audio_url is empty")
                raise Exception("Audio stream kagak ketemu.")

            filename = audio_url

            # =========================
            # Dynamic FFmpeg Headers
            # =========================
            before_options = (
                "-reconnect 1 "
                "-reconnect_streamed 1 "
                "-reconnect_delay_max 5 "
            )

            for key, value in headers.items():
                before_options += (
                    f'-headers "{key}: {value}\\r\\n" '
                )

            logger.debug(
                f"[ffmpeg] before_options={before_options}"
            )

            ffmpeg_source = discord.FFmpegPCMAudio(
                filename,
                before_options=before_options,
                options="-vn",
            )

        else:
            filename = ytdl.prepare_filename(data)

            logger.debug(
                f"[yt-dlp] Using downloaded file | "
                f"filename={filename}"
            )

            ffmpeg_source = discord.FFmpegPCMAudio(
                filename,
                options="-vn",
            )

        logger.debug(f"[yt-dlp] FINAL AUDIO URL = {filename}")

        return cls(
            ffmpeg_source,
            data=data,
        )

    @classmethod
    async def from_url(cls, url: str, *, loop=None, stream: bool = False):
        loop = loop or asyncio.get_event_loop()

        logger.debug(f"[yt-dlp] from_url called | url={url!r} stream={stream}")
        logger.debug(f"[yt-dlp] format={ytdl_format_options.get('format')} | player_client={ytdl_format_options.get('extractor_args', {}).get('youtube', {}).get('player_client')} | cookiefile={ytdl_format_options.get('cookiefile')}")

        try:
            data = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(url, download=not stream),
            )
        except Exception as e:
            logger.error(f"❌ yt-dlp error: {e}")
            logger.error(f"[yt-dlp] FULL ERROR | url={url!r} | type={type(e).__name__} | msg={str(e)}")
            msg = str(e)

            if (
                "Sign in to confirm you're not a bot" in msg
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

            if "Requested format is not available" in msg:
                raise Exception(
                    "Format lagu tidak tersedia. YouTube mungkin membatasi akses."
                )

            raise

        if not data:
            raise Exception("Data lagu kosong. YouTube/yt-dlp kagak ngasih hasil.")

        logger.debug(f"[yt-dlp] extract_info OK | id={data.get('id')} title={data.get('title')!r} extractor={data.get('extractor')} formats_count={len(data.get('formats', []))}")

        if "entries" in data:
            entries = [entry for entry in data["entries"] if entry]
            if not entries:
                raise Exception("Playlist/search result kosong.")

            if data.get("_type") == "playlist":
                return data

            data = entries[0]
            logger.debug(f"[yt-dlp] using first entry | id={data.get('id')} title={data.get('title')!r}")

        return await cls.create_source(data, stream=stream)


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

    def handle_next(self, error):
        if error:
            logger.error(f"Player error: {error}")
        self.next.set()

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
                after=lambda e: self.interaction.client.loop.call_soon_threadsafe(
                    self.handle_next, e
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

def spotify_to_queries(url: str) -> tuple[list[str], Optional[str]]:
    if not sp:
        raise Exception("Fitur Spotify kagak dikonfigurasi sama mod-nya.")

    queries = []
    info = None

    try:
        if "track" in url:
            track = sp.track(url)
            queries.append(f"{track['name']} {track['artists'][0]['name']}")
            info = f"ℹ️ Menambahkan lagu Spotify: **{track['name']}**"
        
        elif "album" in url:
            album = sp.album(url)
            for item in album["tracks"]["items"]:
                queries.append(f"{item['name']} {album['artists'][0]['name']}")
            info = f"ℹ️ Menambahkan **{len(queries)}** lagu dari album Spotify: **{album['name']}**"

        elif "playlist" in url:
            results = sp.playlist_items(url)
            tracks = results['items']
            while results['next']:
                results = sp.next(results)
                tracks.extend(results['items'])
            
            for item in tracks:
                if item['track']:
                    track = item['track']
                    queries.append(f"{track['name']} {track['artists'][0]['name']}")
            
            playlist_info = sp.playlist(url, fields="name")
            info = f"ℹ️ Menambahkan **{len(queries)}** lagu dari playlist Spotify: **{playlist_info['name']}**"

        elif "artist" in url:
            artist = sp.artist(url)
            top_tracks = sp.artist_top_tracks(url)
            for track in top_tracks['tracks']:
                queries.append(f"{track['name']} {artist['name']}")
            info = f"ℹ️ Menambahkan **{len(queries)}** lagu terpopuler dari artist Spotify: **{artist['name']}**"
        
        else:
            raise Exception("Link Spotify-nya kagak dikenali.")

    except Exception as e:
        logger.error(f"Spotify extraction error: {e}")
        raise Exception(f"Gagal ngambil data dari Spotify: {e}")

    return queries, info


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
        try:
            await interaction.response.defer()
        except discord.NotFound:
            await interaction.channel.send("❌ Interaksi expired, coba lagi deh. Bot lagi lag kayaknya.")
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                "❌ Lu harus join voice channel dulu lah!"
            )

        try:
            voice_channel = interaction.user.voice.channel

            if not interaction.guild.voice_client:
                try:
                    logger.info("Connecting to voice channel...")

                    await voice_channel.connect(
                        self_deaf=True,
                        self_mute=False,
                        reconnect=True,
                    )
                except asyncio.TimeoutError:
                    return await interaction.followup.send(
                        "❌ Timeout connect ke voice channel Discord."
                    )
                except Exception as e:
                    return await interaction.followup.send(
                        f"❌ Gagal connect voice: {e}"
                    )
            elif interaction.guild.voice_client.channel != voice_channel:
                await interaction.guild.voice_client.move_to(voice_channel)
                await interaction.guild.voice_client.edit(deafen=True, mute=False)

            queries = [search]
            info_message = None

            if "spotify.com" in search:
                queries, info_message = spotify_to_queries(search)

                if info_message:
                    await interaction.followup.send(info_message)

            player = get_player(interaction)

            for i, query in enumerate(queries):
                try:
                    if i == 0:
                        await interaction.followup.send(f"🔎 Nyari: **{query}**...")

                    result = await YTDLSource.from_url(
                        query,
                        loop=asyncio.get_running_loop(),
                        stream=True,
                    )

                    # Jika hasil adalah playlist (dict yang punya 'entries')
                    if isinstance(result, dict) and "entries" in result:
                        entries = [e for e in result["entries"] if e]
                        total_entries = len(entries)
                        
                        if total_entries > 0:
                            playlist_title = result.get("title", "YouTube Playlist")
                            await interaction.channel.send(f"ℹ️ Menambahkan **{total_entries}** lagu dari playlist YouTube: **{playlist_title}**")
                        
                        for entry_idx, entry in enumerate(entries):
                            try:
                                source = await YTDLSource.create_source(entry, stream=True)
                                await player.queue.put(source)
                                
                                if entry_idx == 0 and i == 0 and not player.current:
                                    await interaction.followup.send(f"✅ Dapet! Siap diputer: **{source.title}**")
                            except Exception as inner_e:
                                logger.error(f"Error processing entry {entry_idx}: {inner_e}")
                        
                        continue

                    # Jika hasil adalah single source (objek YTDLSource)
                    source = result
                    await player.queue.put(source)

                    if i == 0:
                        if player.current:
                            await interaction.followup.send(
                                f"✅ Ditambahin ke antrean: **{source.title}**"
                            )
                        else:
                            await interaction.followup.send(
                                f"✅ Dapet! Siap diputer: **{source.title}**"
                            )
                except Exception as e:
                    logger.error(f"Error processing query '{query}': {e}")
                    if i == 0:
                        await interaction.followup.send(f"❌ Gagal muter **{query}**: {e}")
                    else:
                        await interaction.channel.send(f"❌ Gagal nambahin **{query}** ke antrean.")

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

        if player.queue.empty() and not player.current:
            return await interaction.response.send_message(
                "📭 Antrean kosong, kayak hati lu."
            )

        upcoming = list(player.queue._queue.copy())
        fmt = ""
        if player.current:
            fmt += f"**Sekarang diputar:** {player.current.title}\n\n"
        
        if upcoming:
            fmt += "**Antrean:**\n"
            fmt += "\n".join(
                f"{i + 1}. **{source.title}**"
                for i, source in enumerate(upcoming[:10])
            )

            if len(upcoming) > 10:
                fmt += f"\n...dan {len(upcoming) - 10} lagu lainnya."
        
        embed = discord.Embed(
            title=f"Antrean Lagunya Kakak",
            description=fmt,
        )

        await interaction.response.send_message(embed=embed)

    async def _fetch_lyrics(artist: str, title: str) -> Optional[str]:
        url = f"https://api.lyrics.ovh/v1/{quote(artist)}/{quote(title)}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        return data.get("lyrics")
                    return None
            except Exception as e:
                logger.error(f"Lyrics fetch error: {e}")
                return None

    async def _auto_lyrics(interaction: discord.Interaction) -> tuple[Optional[str], Optional[str]]:
        player = players.get(interaction.guild_id)
        if not player or not player.current:
            return None, None

        full_title = player.current.title
        separators = [" - ", " | ", " — ", " – "]
        for sep in separators:
            if sep in full_title:
                parts = full_title.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        if " " in full_title:
            words = full_title.split(" ")
            return words[0], " ".join(words[1:])

        return None, full_title

    @tree.command(
        name="lyrics",
        description="Cari lirik lagu (otomatis dari lagu yang lagi diputar, atau manual)",
        guild=TEST_GUILD,
    )
    @app_commands.describe(
        artist="Nama artis (opsional kalau lagi muter lagu)",
        title="Judul lagu (opsional kalau lagi muter lagu)",
    )
    async def lyrics(
        interaction: discord.Interaction,
        artist: Optional[str] = None,
        title: Optional[str] = None,
    ):
        try:
            await interaction.response.defer()
        except discord.NotFound:
            await interaction.channel.send("❌ Interaksi expired, coba lagi deh. Bot lagi lag kayaknya.")
            return

        if not artist and not title:
            artist, title = await _auto_lyrics(interaction)
            if not artist and not title:
                return await interaction.followup.send(
                    "❌ Kagak ada lagu yang lagi diputar, dan lu juga kagak kasih judul. Mau cari lirik apaan?"
                )

        query_display = f"{artist} - {title}" if artist else title

        await interaction.followup.send(f"🔎 Nyari lirik: **{query_display}**...")

        lyrics_text = await _fetch_lyrics(artist or "", title or "")

        if not lyrics_text:
            return await interaction.followup.send(
                f"❌ Lirik buat **{query_display}** kagak ketemu. Coba tulis nama artis dan judulnya lebih spesifik."
            )

        lyrics_text = lyrics_text.strip()

        if len(lyrics_text) <= 4096:
            embed = discord.Embed(
                title=f"🎤 Lirik: {query_display}",
                description=lyrics_text[:4096],
                color=discord.Color.blurple(),
            )
            if len(lyrics_text) > 2048:
                embed.description = lyrics_text[:2048]
                remaining = lyrics_text[2048:]
                await interaction.followup.send(embed=embed)
                chunks = [remaining[i:i + 2000] for i in range(0, len(remaining), 2000)]
                for chunk in chunks:
                    await interaction.followup.send(
                        embed=discord.Embed(description=chunk, color=discord.Color.blurple())
                    )
            else:
                await interaction.followup.send(embed=embed)
        else:
            chunks = [lyrics_text[i:i + 4096] for i in range(0, len(lyrics_text), 4096)]
            for idx, chunk in enumerate(chunks):
                embed = discord.Embed(
                    title=f"🎤 Lirik: {query_display} (bagian {idx + 1}/{len(chunks)})" if len(chunks) > 1 else f"🎤 Lirik: {query_display}",
                    description=chunk,
                    color=discord.Color.blurple(),
                )
                await interaction.followup.send(embed=embed)