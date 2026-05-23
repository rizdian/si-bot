import asyncio
import logging

import discord

from .source import YTDLSource
from .player import MusicPlayer, get_player, players
from .spotify import spotify_to_queries, spotify_search_track
from .embeds import error_embed, success_embed, info_embed

logger = logging.getLogger("bot")


class FakeInteraction:
    def __init__(self, guild, user, channel, client):
        self.guild = guild
        self.guild_id = guild.id
        self.user = user
        self.channel = channel
        self.client = client


async def _ensure_voice_connection(
    guild: discord.Guild,
    voice_channel: discord.VoiceChannel,
) -> bool:
    if not guild.voice_client:
        try:
            await voice_channel.connect(self_deaf=True, self_mute=False, reconnect=True)
        except (asyncio.TimeoutError, Exception):
            return False
    elif guild.voice_client.channel != voice_channel:
        await guild.voice_client.move_to(voice_channel)
        await guild.voice_client.edit(deafen=True, mute=False)
    return True


async def _enqueue_entries(
    entries: list,
    player: MusicPlayer,
    requester: discord.Member,
    channel: discord.TextChannel,
    playlist_title: str,
    silent: bool = False,
) -> tuple[int, int]:
    added = 0
    failed = 0
    for entry in entries:
        try:
            source = await YTDLSource.create_source(entry, stream=True)
            source.requester = requester
            await player.queue.put(source)
            added += 1
        except Exception as e:
            failed += 1
            logger.error("Error processing playlist entry: %s", e)

    if not silent:
        parts = [f"✅ **{added}** lagu ditambahkan ke antrean dari: **{playlist_title}**"]
        if failed:
            parts.append(f"⚠️ {failed} lagu gagal ditambahkan.")
        await channel.send(embed=info_embed("\n".join(parts)))

    return added, failed


async def do_play(
    search: str,
    guild: discord.Guild,
    voice_channel: discord.VoiceChannel,
    send: callable,
    channel: discord.TextChannel,
    requester: discord.Member,
    client: discord.Client,
) -> None:
    if not await _ensure_voice_connection(guild, voice_channel):
        return await send(embed=error_embed("Gagal connect ke voice channel."))

    queries = [search]
    info_message = None

    if "spotify.com" in search:
        try:
            queries, info_message = spotify_to_queries(search)
        except Exception as e:
            return await send(embed=error_embed(f"{e}"))
        if info_message:
            await send(embed=info_embed(info_message))
    elif not search.startswith(("http://", "https://")):
        spotify_query = spotify_search_track(search)
        if spotify_query:
            queries = [spotify_query]

    fake = FakeInteraction(guild, requester, channel, client)
    player = get_player(fake)
    player.vc = guild.voice_client

    is_batch = len(queries) > 1

    if is_batch:
        await send(embed=info_embed(f"🔎 Memproses **{len(queries)}** lagu..."))
        added = 0
        failed = 0
        for query in queries:
            try:
                result = await YTDLSource.from_url(
                    query, loop=asyncio.get_running_loop(), stream=True,
                )
                if isinstance(result, dict) and "entries" in result:
                    entries = [e for e in result["entries"] if e]
                    if entries:
                        a, _ = await _enqueue_entries(
                            entries, player, requester, channel,
                            result.get("title", "YouTube Playlist"),
                            silent=True,
                        )
                        added += a
                else:
                    result.requester = requester
                    await player.queue.put(result)
                    added += 1
            except Exception as e:
                failed += 1
                logger.error("Error processing query '%s': %s", query, e)

        parts = [f"✅ **{added}** lagu ditambahkan ke antrean"]
        if failed:
            parts.append(f"⚠️ {failed} lagu gagal ditambahkan.")
        await send(embed=success_embed("\n".join(parts)))
        return

    query = queries[0]
    try:
        await send(embed=info_embed(f"🔎 Mencari: **{query}**..."))

        result = await YTDLSource.from_url(
            query, loop=asyncio.get_running_loop(), stream=True,
        )

        if isinstance(result, dict) and "entries" in result:
            entries = [e for e in result["entries"] if e]
            if entries:
                await _enqueue_entries(
                    entries, player, requester, channel,
                    result.get("title", "YouTube Playlist"),
                )
            return

        result.requester = requester
        await player.queue.put(result)

        msg = (
            f"Ditambahkan ke antrean: **{result.title}**"
            if player.current
            else f"Ditemukan! Siap diputar: **{result.title}**"
        )
        await send(embed=success_embed(f"✅ {msg}"))

    except Exception as e:
        logger.error("Error processing query '%s': %s", query, e)
        await send(embed=error_embed(f"Gagal memutar **{query}**: {e}"))
