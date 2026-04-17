from datetime import datetime, timezone
from typing import Iterable, Optional

import discord
from config import LOG_CHANNEL_ID


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
        print("❌ LOG_CHANNEL_ID belum diset!")
        return

    channel = client.get_channel(LOG_CHANNEL_ID)
    if not channel:
        print(f"❌ Channel log dengan ID {LOG_CHANNEL_ID} tidak ditemukan!")
        return

    if not isinstance(channel, discord.TextChannel):
        print(f"❌ Channel ID {LOG_CHANNEL_ID} bukan TextChannel!")
        return

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