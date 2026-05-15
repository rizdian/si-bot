import asyncio
import logging
from typing import Optional

import discord
import yt_dlp

from utils.redis_cache import get_cached, set_cached, set_meta

logger = logging.getLogger("bot")

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_YTDL_FORMAT_OPTIONS = {
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
    "js_runtimes": {"node": {}},
    "remote_components": ["ejs:github"],
    "extractor_args": {
        "youtube": {
            "player_client": ["web_creator", "android_vr", "web"],
        }
    },
    "http_headers": {
        "User-Agent": _USER_AGENT,
        "Referer": "https://www.youtube.com/",
    },
}

ytdl = yt_dlp.YoutubeDL(_YTDL_FORMAT_OPTIONS)


def _select_audio_format(data: dict) -> Optional[tuple[str, dict]]:
    headers = data.get("http_headers", {})

    for fmt in data.get("requested_formats", []):
        if fmt.get("acodec") != "none":
            logger.debug("Using requested_format itag=%s", fmt.get("format_id"))
            url = fmt.get("url")
            if url:
                return url, headers

    audio_formats = [f for f in data.get("formats", []) if f.get("acodec") != "none"]
    audio_only = [f for f in audio_formats if f.get("vcodec") == "none"]

    pool = audio_only or audio_formats
    if pool:
        best = max(pool, key=lambda f: f.get("abr") or 0)
        logger.debug(
            "Selected stream itag=%s ext=%s abr=%s",
            best.get("format_id"), best.get("ext"), best.get("abr"),
        )
        url = best.get("url")
        if url:
            return url, headers

    return None


def _resolve_stream_url(data: dict) -> tuple[str, dict]:
    result = _select_audio_format(data)
    if result:
        return result

    fallback = data.get("url")
    if not fallback:
        raise Exception("Audio stream tidak ditemukan.")

    logger.warning("Falling back to data['url']")
    return fallback, data.get("http_headers", {})


def _build_ffmpeg_audio(url: str, headers: dict) -> discord.FFmpegPCMAudio:
    before_options = (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
    )
    for key, value in headers.items():
        before_options += f'-headers "{key}: {value}\r\n" '

    return discord.FFmpegPCMAudio(url, before_options=before_options, options="-vn")


def _translate_ytdl_error(exc: Exception) -> Exception:
    msg = str(exc).lower()
    if "sign in to confirm" in msg or "not a bot" in msg or "memblokir" in msg:
        return Exception(
            "YouTube memblokir bot. "
            "Pastikan `cookies.txt` valid dan sudah di-mount ke `/app/cookies.txt`."
        )
    if "403" in msg or "forbidden" in msg:
        return Exception(
            "Error 403 Forbidden. Coba export ulang `cookies.txt` atau update yt-dlp."
        )
    if "requested format is not available" in msg:
        return Exception("Format lagu tidak tersedia. YouTube mungkin membatasi akses.")
    return exc


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume: float = 0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title", "Unknown Title")
        self.url = data.get("url")
        self.webpage_url = data.get("webpage_url")
        self.requester = None

    @classmethod
    async def create_source(cls, data: dict, *, stream: bool = False):
        if not data:
            raise Exception("Data lagu kosong.")

        if stream:
            audio_url, headers = _resolve_stream_url(data)
            ffmpeg_source = _build_ffmpeg_audio(audio_url, headers)
        else:
            filename = ytdl.prepare_filename(data)
            logger.debug("Using downloaded file: %s", filename)
            ffmpeg_source = discord.FFmpegPCMAudio(filename, options="-vn")

        logger.info("Audio source ready: %s", data.get("title", "unknown"))
        return cls(ffmpeg_source, data=data)

    @classmethod
    async def from_url(cls, url: str, *, loop=None, stream: bool = False):
        loop = loop or asyncio.get_event_loop()

        cached = await get_cached(url)
        if cached:
            logger.info("Cache hit for: %s", url)
            data = cached
        else:
            try:
                data = await loop.run_in_executor(
                    None, lambda: ytdl.extract_info(url, download=not stream),
                )
            except Exception as e:
                raise _translate_ytdl_error(e) from e

            if not data:
                raise Exception("Data lagu kosong. YouTube/yt-dlp tidak memberikan hasil.")

            if "entries" in data:
                entries = [e for e in data["entries"] if e]
                if not entries:
                    raise Exception("Playlist/search result kosong.")
                if data.get("_type") == "playlist":
                    await set_cached(url, data)
                    return data
                data = entries[0]

            await set_cached(url, data)
            video_id = data.get("id")
            if video_id:
                await set_meta(video_id, data)

        if not data:
            raise Exception("Data lagu kosong.")

        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            if not entries:
                raise Exception("Playlist/search result kosong.")
            if data.get("_type") == "playlist":
                return data
            data = entries[0]

        return await cls.create_source(data, stream=stream)


async def get_related_video_url(data: dict, loop=None) -> str | None:
    related = data.get("related_videos")
    if not related:
        return None
    for video in related:
        video_id = video.get("id")
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    return None
