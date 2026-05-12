import logging
from typing import Optional
from urllib.parse import quote

import aiohttp
import discord

logger = logging.getLogger("bot")


async def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    url = f"https://api.lyrics.ovh/v1/{quote(artist)}/{quote(title)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data.get("lyrics")
    except Exception as e:
        logger.error("Lyrics fetch error: %s", e)
    return None


def extract_artist_title(player) -> tuple[Optional[str], Optional[str]]:
    if not player or not player.current:
        return None, None
    full_title = player.current.title
    for sep in (" - ", " | ", " — ", " – "):
        if sep in full_title:
            parts = full_title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    if " " in full_title:
        words = full_title.split(" ")
        return words[0], " ".join(words[1:])
    return None, full_title


async def send_lyrics(send_fn, query_display: str, lyrics_text: str):
    lyrics_text = lyrics_text.strip()
    if not lyrics_text:
        return

    if len(lyrics_text) <= 2048:
        embed = discord.Embed(
            title=f"🎤 Lirik: {query_display}",
            description=lyrics_text,
            color=discord.Color.blurple(),
        )
        await send_fn(embed=embed)
        return

    embed = discord.Embed(
        title=f"🎤 Lirik: {query_display}",
        description=lyrics_text[:2048],
        color=discord.Color.blurple(),
    )
    await send_fn(embed=embed)

    remaining = lyrics_text[2048:]
    for i in range(0, len(remaining), 2000):
        await send_fn(embed=discord.Embed(
            description=remaining[i:i + 2000],
            color=discord.Color.blurple(),
        ))
