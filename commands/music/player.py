import asyncio
import logging
import time
from collections import deque
from typing import Optional

import discord

from config import OWNER_USER_ID
from .source import YTDLSource, get_related_video_url
from .spotify import ai_recommend_music
from .embeds import build_now_playing_embed, error_embed, success_embed, warning_embed, info_embed
from .lyrics import fetch_lyrics, extract_artist_title, send_lyrics
from utils.redis_cache import invalidate

logger = logging.getLogger("bot")

_LOOP_MODES = ("off", "track", "queue")
_LOOP_LABELS = ("Loop: Off", "Loop: Track", "Loop: Queue")
_LOOP_EMOJIS = ("🔁", "🔂", "🔁")
_LOOP_COLORS = (
    discord.ButtonStyle.secondary,
    discord.ButtonStyle.success,
    discord.ButtonStyle.success,
)


_QUEUE_PAGE_SIZE = 10


class QueuePaginationView(discord.ui.View):
    def __init__(self, upcoming: list):
        super().__init__(timeout=60)
        self.upcoming = upcoming
        self.page = 0
        self.max_page = max(0, (len(upcoming) - 1) // _QUEUE_PAGE_SIZE)

    def build_embed(self) -> discord.Embed:
        start = self.page * _QUEUE_PAGE_SIZE
        end = start + _QUEUE_PAGE_SIZE
        text = "\n".join(
            f"{i + 1}. {item.title}" for i, item in enumerate(self.upcoming[start:end], start=start)
        )
        return discord.Embed(
            title=f"📜 Queue ({len(self.upcoming)} lagu)",
            description=text,
            color=discord.Color.blurple(),
        ).set_footer(text=f"Halaman {self.page + 1}/{self.max_page + 1}")

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page <= 0:
            return await interaction.response.defer()
        self.page -= 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page >= self.max_page:
            return await interaction.response.defer()
        self.page += 1
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class MusicControllerView(discord.ui.View):
    _skip_cooldowns: dict[int, float] = {}
    _SKIP_COOLDOWN = 60

    def __init__(self, player: "MusicPlayer"):
        super().__init__(timeout=None)
        self.player = player
        self._sync_buttons()

    def _check_voice(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return "Kamu harus join voice channel dulu!"
        vc = interaction.guild.voice_client
        if vc and interaction.user.voice.channel != vc.channel:
            return "Kamu harus di voice channel yang sama dengan bot!"
        return None

    def _sync_buttons(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if "Loop" in (item.label or ""):
                    idx = {"off": 0, "track": 1, "queue": 2}.get(self.player.loop_mode, 0)
                    item.label = _LOOP_LABELS[idx]
                    item.emoji = _LOOP_EMOJIS[idx]
                    item.style = _LOOP_COLORS[idx]
                elif "Autoplay" in (item.label or ""):
                    if self.player.autoplay:
                        item.label = "Autoplay: On"
                        item.style = discord.ButtonStyle.success
                    else:
                        item.label = "Autoplay: Off"
                        item.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc:
            return await interaction.response.send_message(
                embed=error_embed("Bot tidak ada di VC."), ephemeral=True,
            )
        if not vc.is_playing() and not vc.is_paused():
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada lagu yang diputar."), ephemeral=True,
            )

        if vc.is_paused():
            vc.resume()
            button.label, button.emoji = "Pause", "⏸️"
            action = "Resume"
        else:
            vc.pause()
            button.label, button.emoji = "Resume", "▶️"
            action = "Pause"

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            embed=success_embed(f"{action} oleh {interaction.user.mention}"),
            ephemeral=False,
        )

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada lagu yang diputar."), ephemeral=True,
            )

        now = time.time()
        last = self._skip_cooldowns.get(interaction.user.id, 0)
        remaining = int(self._SKIP_COOLDOWN - (now - last))
        if remaining > 0:
            return await interaction.response.send_message(
                embed=warning_embed(f"⏳ Tunggu **{remaining}** detik lagi sebelum skip."), ephemeral=True,
            )

        self._skip_cooldowns[interaction.user.id] = now
        vc.stop()
        await interaction.response.send_message(
            embed=success_embed(f"⏭️ Lagu diskip oleh {interaction.user.mention}"), ephemeral=True,
        )

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        if interaction.user.id != OWNER_USER_ID:
            return await interaction.response.send_message(
                embed=error_embed("❌ Kamu bukan owner."), ephemeral=True
            )

        vc = interaction.guild.voice_client
        player = players.get(interaction.guild_id)
        if player:
            player.autoplay = False
            player._cancel_prefetch()
        if vc:
            vc.stop()
            await vc.disconnect()
        players.pop(interaction.guild_id, None)
        await interaction.response.edit_message(
            embed=success_embed(f"👋 Playback dihentikan oleh {interaction.user.mention}."),
            view=None,
        )

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.primary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        player = players.get(interaction.guild_id)
        upcoming = list(player.queue._queue) if player else []
        if not upcoming:
            return await interaction.response.send_message(
                embed=warning_embed("📭 Queue kosong."), ephemeral=True,
            )

        view = QueuePaginationView(upcoming)
        embed = view.build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Loop: Off", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        player = players.get(interaction.guild_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada player aktif."), ephemeral=True,
            )

        current = _LOOP_MODES.index(player.loop_mode)
        nxt = (current + 1) % len(_LOOP_MODES)

        player.loop_mode = _LOOP_MODES[nxt]
        button.label = _LOOP_LABELS[nxt]
        button.emoji = _LOOP_EMOJIS[nxt]
        button.style = _LOOP_COLORS[nxt]

        if nxt == 0:
            player._played_sources.clear()

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            embed=success_embed(f"🔁 {_LOOP_LABELS[nxt]} oleh {interaction.user.mention}"),
            ephemeral=False,
        )

    @discord.ui.button(label="Autoplay: Off", emoji="🔀", style=discord.ButtonStyle.secondary)
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        player = players.get(interaction.guild_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada player aktif."), ephemeral=True,
            )

        player.autoplay = not player.autoplay

        if player.autoplay:
            button.label = "Autoplay: On"
            button.emoji = "🔀"
            button.style = discord.ButtonStyle.success
        else:
            button.label = "Autoplay: Off"
            button.emoji = "🔀"
            button.style = discord.ButtonStyle.secondary
            player._cancel_prefetch()

        await interaction.response.edit_message(view=self)
        state = "On" if player.autoplay else "Off"
        await interaction.followup.send(
            embed=success_embed(f"🔀 Autoplay: {state} oleh {interaction.user.mention}"),
            ephemeral=False,
        )

    @discord.ui.button(label="Lyrics", emoji="🎤", style=discord.ButtonStyle.secondary)
    async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        err = self._check_voice(interaction)
        if err:
            return await interaction.response.send_message(embed=error_embed(err), ephemeral=True)
        player = players.get(interaction.guild_id)
        if not player or not player.current:
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada lagu yang sedang diputar."), ephemeral=True,
            )

        await interaction.response.defer(thinking=True)

        artist, title = extract_artist_title(player)
        if not artist or not title:
            return await interaction.followup.send(
                embed=error_embed("Gagal mengenali judul/artis dari lagu ini."),
            )

        lyrics = await fetch_lyrics(artist, title)
        if not lyrics:
            return await interaction.followup.send(
                embed=warning_embed(f"Lirik tidak ditemukan untuk **{artist} - {title}**."),
            )

        await send_lyrics(
            lambda **kwargs: interaction.followup.send(**kwargs),
            f"{artist} - {title}",
            lyrics,
        )


class MusicPlayer:
    LOOP_OFF = "off"
    LOOP_TRACK = "track"
    LOOP_QUEUE = "queue"

    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.queue: asyncio.Queue[YTDLSource] = asyncio.Queue()
        self.next = asyncio.Event()
        self.current: Optional[YTDLSource] = None
        self.vc: Optional[discord.VoiceClient] = interaction.guild.voice_client
        self.now_playing_message: Optional[discord.Message] = None
        self.loop_mode: str = self.LOOP_OFF
        self.autoplay: bool = False
        self._last_source: Optional[YTDLSource] = None
        self._played_sources: list[YTDLSource] = []
        self._autoplay_history: deque[str] = deque(maxlen=50)
        self._prefetch_task: Optional[asyncio.Task] = None
        self._prefetched_query: Optional[tuple[str, str]] = None
        self._playback_error: Optional[str] = None

        interaction.client.loop.create_task(self.player_loop())

    async def _send_error(self, error):
        logger.error("Player error: %s", error)
        err_str = str(error)
        if "403" in err_str or "Forbidden" in err_str:
            if self.current:
                query = self.current.webpage_url or self.current.title
                await invalidate(query)
            msg = "**Gagal memutar lagu** (403 Forbidden).\nCache diinvalidate, coba ulang pake `/play judul artis` ya."
        else:
            msg = f"**Error:** {err_str}\nSilahkan ulang pake `/play judul artis` ya."

        target = self.now_playing_message.channel if self.now_playing_message else self.interaction.channel
        try:
            await target.send(embed=error_embed(msg))
        except Exception:
            pass

    def _handle_next(self, error):
        if error:
            self._playback_error = str(error)
            self.interaction.client.loop.create_task(self._send_error(error))
        else:
            self._playback_error = None
        self.next.set()

    async def player_loop(self):
        await self.interaction.client.wait_until_ready()

        while not self.interaction.client.is_closed():
            self.next.clear()
            await self._refill_queue_if_looping()

            if self.queue.empty() and self.autoplay and self._last_source:
                await self._autoplay_related()

            try:
                source = await self.queue.get()
            except asyncio.CancelledError:
                break

            self.current = source
            if not self.vc or not self.vc.is_connected():
                self._cancel_prefetch()
                self.current = None
                continue

            if self.autoplay and self.queue.empty() and not self.loop_mode == self.LOOP_TRACK:
                self._start_prefetch(source)

            self.vc.play(
                source,
                after=lambda e: self.interaction.client.loop.call_soon_threadsafe(
                    self._handle_next, e,
                ),
            )

            await self._send_now_playing(source)

            await self.next.wait()

            playback_err = self._playback_error
            source.cleanup()

            if playback_err and getattr(source, "_from_autoplay", False):
                retry_ok = await self._retry_play(source)
                if retry_ok:
                    continue

            await self._handle_loop_after_play(source)
            self._last_source = source
            self.current = None

    async def _refill_queue_if_looping(self):
        if not self.queue.empty() or not self._played_sources or self.loop_mode != self.LOOP_QUEUE:
            return
        for src in self._played_sources:
            try:
                new_source = await YTDLSource.from_url(
                    src.webpage_url or src.title,
                    loop=self.interaction.client.loop,
                    stream=True,
                )
                new_source.requester = src.requester
                await self.queue.put(new_source)
            except Exception as e:
                logger.error("Loop queue re-fetch error for '%s': %s", src.title, e)
        self._played_sources.clear()

    def _is_recently_played(self, title: str) -> bool:
        return title.strip().lower() in self._autoplay_history

    def _record_played(self, title: str):
        self._autoplay_history.append(title.strip().lower())

    def _get_exclude_titles(self) -> set[str]:
        return set(self._autoplay_history)

    def _get_exclude_video_ids(self, source: YTDLSource) -> set[str]:
        ids = set()
        if source.data:
            ids.add(source.data.get("id", ""))
        for src in self._played_sources:
            if src.data:
                vid = src.data.get("id")
                if vid:
                    ids.add(vid)
        return ids

    async def _resolve_autoplay_query(self, source: YTDLSource) -> tuple[str, str]:
        title = source.title or ""
        exclude_titles = self._get_exclude_titles()
        exclude_ids = self._get_exclude_video_ids(source)

        ai_session = self.interaction.client.ai_session
        query = await ai_recommend_music(
            title, exclude=exclude_titles, session=ai_session,
        )
        if query:
            return query, "AI Recommend"

        related_url = await get_related_video_url(
            source.data, exclude_ids=exclude_ids,
        )
        if related_url:
            return related_url, "YouTube Related"

        return f"ytsearch1:{title}", "YouTube Search"

    async def _fetch_source_from_query(self, query: str) -> Optional[YTDLSource]:
        result = await YTDLSource.from_url(
            query, loop=self.interaction.client.loop, stream=True,
        )

        if isinstance(result, dict) and "entries" in result:
            entries = [e for e in result["entries"] if e]
            if not entries:
                return None
            return await YTDLSource.create_source(entries[0], stream=True)

        return result

    def _cancel_prefetch(self):
        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()
        self._prefetch_task = None
        self._prefetched_query = None

    def _start_prefetch(self, source: YTDLSource):
        self._cancel_prefetch()

        async def _do_prefetch():
            try:
                if not self.vc or not self.vc.is_connected():
                    return
                query, label = await self._resolve_autoplay_query(source)
                if not self.vc or not self.vc.is_connected():
                    return
                self._prefetched_query = (query, label)
                logger.info("Prefetch [%s]: query '%s'", label, query)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("Prefetch failed: %s", e)

        self._prefetch_task = self.interaction.client.loop.create_task(_do_prefetch())

    async def _retry_play(self, source: YTDLSource) -> bool:
        if not self.vc or not self.vc.is_connected():
            return False

        query = source.webpage_url or source.title
        if not query:
            return False

        try:
            await invalidate(query)
            logger.info("Retry: re-fetching '%s'", source.title)

            new_source = await YTDLSource.from_url(
                query, loop=self.interaction.client.loop, stream=True,
            )

            if isinstance(new_source, dict) and "entries" in new_source:
                entries = [e for e in new_source["entries"] if e]
                if not entries:
                    return False
                new_source = await YTDLSource.create_source(entries[0], stream=True)

            new_source.requester = source.requester
            new_source._from_autoplay = True

            self.current = new_source
            self.next.clear()

            self.vc.play(
                new_source,
                after=lambda e: self.interaction.client.loop.call_soon_threadsafe(
                    self._handle_next, e,
                ),
            )

            await self.next.wait()
            new_source.cleanup()

            if self._playback_error:
                logger.error("Retry also failed for '%s'", source.title)
                return False

            logger.info("Retry success for '%s'", source.title)
            return True
        except Exception as e:
            logger.error("Retry exception for '%s': %s", source.title, e)
            return False

    async def _autoplay_related(self):
        if self._prefetched_query:
            query, label = self._prefetched_query
            self._prefetched_query = None
            self._prefetch_task = None
            try:
                source = await self._fetch_source_from_query(query)
                if source:
                    source.requester = self.interaction.guild.me
                    source._from_autoplay = True
                    await self.queue.put(source)
                    self._record_played(source.title)
                    logger.info("Autoplay [Prefetch %s]: enqueued '%s'", label, source.title)
                    target = self.now_playing_message.channel if self.now_playing_message else self.interaction.channel
                    await target.send(embed=info_embed(f"🔀 **Autoplay:** {source.title}"))
                    return
            except Exception as e:
                logger.warning("Autoplay prefetch fetch failed: %s", e)

        if self._prefetch_task and not self._prefetch_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._prefetch_task), timeout=15)
            except (asyncio.TimeoutError, Exception):
                pass

            if self._prefetched_query:
                query, label = self._prefetched_query
                self._prefetched_query = None
                self._prefetch_task = None
                try:
                    source = await self._fetch_source_from_query(query)
                    if source:
                        source.requester = self.interaction.guild.me
                        source._from_autoplay = True
                        await self.queue.put(source)
                        self._record_played(source.title)
                        logger.info("Autoplay [Prefetch late %s]: enqueued '%s'", label, source.title)
                        target = self.now_playing_message.channel if self.now_playing_message else self.interaction.channel
                        await target.send(embed=info_embed(f"🔀 **Autoplay:** {source.title}"))
                        return
                except Exception as e:
                    logger.warning("Autoplay prefetch late fetch failed: %s", e)

        last_source = self._last_source
        if not last_source:
            return

        try:
            query, source_label = await self._resolve_autoplay_query(last_source)
            source = await self._fetch_source_from_query(query)
            if not source:
                return

            source.requester = self.interaction.guild.me
            source._from_autoplay = True
            await self.queue.put(source)
            self._record_played(source.title)
            logger.info("Autoplay [%s]: enqueued '%s'", source_label, source.title)

            target = self.now_playing_message.channel if self.now_playing_message else self.interaction.channel
            await target.send(embed=info_embed(f"🔀 **Autoplay:** {source.title}"))
        except Exception as e:
            logger.error("Autoplay error: %s", e)

    async def _send_now_playing(self, source: YTDLSource):
        requester = source.requester or self.interaction.user
        embed = build_now_playing_embed(source, requester, self.vc.channel)

        loop_labels = {self.LOOP_TRACK: "🔁 Track", self.LOOP_QUEUE: "🔁 Queue"}
        loop_text = loop_labels.get(self.loop_mode)
        autoplay_text = "🔀 Autoplay" if self.autoplay else None
        parts = [t for t in [loop_text, autoplay_text] if t]
        if parts:
            embed.set_footer(text=" | ".join(parts) + " | Music powered by yt-dlp + FFmpeg")

        view = MusicControllerView(self)

        try:
            if self.now_playing_message:
                try:
                    await self.now_playing_message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
            self.now_playing_message = await self.interaction.channel.send(
                embed=embed, view=view,
            )
        except Exception as e:
            logger.error("Failed to send now playing embed: %s", e)

    async def _handle_loop_after_play(self, source: YTDLSource):
        if self.loop_mode == self.LOOP_TRACK:
            try:
                loop_source = await YTDLSource.from_url(
                    source.webpage_url or source.title,
                    loop=self.interaction.client.loop,
                    stream=True,
                )
                loop_source.requester = source.requester
                await self.queue.put(loop_source)
            except Exception as e:
                logger.error("Loop track re-fetch error: %s", e)
        elif self.loop_mode == self.LOOP_QUEUE:
            self._played_sources.append(source)

    async def destroy(self):
        self._cancel_prefetch()
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()


players: dict[int, MusicPlayer] = {}


def get_player(interaction: discord.Interaction) -> MusicPlayer:
    if interaction.guild_id not in players:
        players[interaction.guild_id] = MusicPlayer(interaction)
    player = players[interaction.guild_id]
    player.vc = interaction.guild.voice_client
    return player
