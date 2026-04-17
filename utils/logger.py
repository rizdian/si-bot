from datetime import datetime, timezone
from typing import Iterable, Optional
import logging

import discord
from config import LOG_CHANNEL_ID


logger = logging.getLogger("discord_logger")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def format_datetime(dt: Optional[datetime], pattern: str = "%Y-%m-%d") -> str:
    if not dt:
        return "-"
    return dt.strftime(pattern)


def truncate_text(text: Optional[str], limit: int = 1024) -> str:
    if not text:
        return "[Empty]"
    return text if len(text) <= limit else text[: limit - 3] + "..."


async def send_log_embed(
    client: discord.Client,
    title: str,
    description: Optional[str] = None,
    color: discord.Color = discord.Color.blue(),
    fields: Optional[Iterable[tuple[str, str, bool]]] = None,
) -> None:
    if not LOG_CHANNEL_ID:
        logger.warning("LOG_CHANNEL_ID belum diset!")
        return

    channel = client.get_channel(LOG_CHANNEL_ID)

    if not channel:
        logger.error("Channel log dengan ID %s tidak ditemukan!", LOG_CHANNEL_ID)
        return

    if not isinstance(channel, discord.TextChannel):
        logger.error("Channel ID %s bukan TextChannel!", LOG_CHANNEL_ID)
        return

    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=now_utc(),
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(
                    name=name,
                    value=truncate_text(str(value), 1024),
                    inline=inline,
                )

        embed.set_footer(text=f"SI BOT • {now_utc().strftime('%H:%M:%S UTC')}")

        await channel.send(embed=embed)

        logger.info("Log embed terkirim: %s", title)

    except Exception:
        logger.exception("Gagal mengirim log embed ke channel")