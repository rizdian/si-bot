import logging

import discord

logger = logging.getLogger("bot")

COLOR_ERROR = discord.Color.red()
COLOR_SUCCESS = discord.Color.green()
COLOR_INFO = discord.Color.blurple()
COLOR_WARNING = discord.Color.orange()


def _format_duration(seconds: float) -> str:
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def build_now_playing_embed(
    source,
    requester: discord.Member | discord.User,
    voice_channel: discord.VoiceChannel,
) -> discord.Embed:
    from .source import YTDLSource

    title = source.data.get("title", "Unknown Title")
    duration = source.data.get("duration")
    duration_text = _format_duration(duration) if duration else "LIVE"
    uploader = source.data.get("uploader")
    thumbnail = source.data.get("thumbnail")
    webpage_url = source.data.get("webpage_url")

    embed = discord.Embed(
        description=(
            "## Now playing\n"
            f"### [{title}]({webpage_url}) ` {duration_text} `\n\n"
            f"> Requested by {requester.mention}\n"
            f"> Connected in 🔊 **{voice_channel.name}**"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )

    if uploader:
        embed.set_author(name=uploader, icon_url=requester.display_avatar.url)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(text="Music powered by yt-dlp + FFmpeg")
    return embed


def error_embed(description: str) -> discord.Embed:
    return discord.Embed(description=description, color=COLOR_ERROR)


def success_embed(description: str) -> discord.Embed:
    return discord.Embed(description=description, color=COLOR_SUCCESS)


def info_embed(description: str) -> discord.Embed:
    return discord.Embed(description=description, color=COLOR_INFO)


def warning_embed(description: str) -> discord.Embed:
    return discord.Embed(description=description, color=COLOR_WARNING)
