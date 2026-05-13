import asyncio
import logging
from typing import Optional

import discord

from .source import YTDLSource, get_related_video_url
from .embeds import build_now_playing_embed, error_embed, success_embed, warning_embed, info_embed

logger = logging.getLogger("bot")

_LOOP_MODES = ("off", "track", "queue")
_LOOP_LABELS = ("Loop: Off", "Loop: Track", "Loop: Queue")
_LOOP_EMOJIS = ("🔁", "🔂", "🔁")
_LOOP_COLORS = (
    discord.ButtonStyle.secondary,
    discord.ButtonStyle.success,
    discord.ButtonStyle.success,
)


class MusicControllerView(discord.ui.View):
    def __init__(self, player: "MusicPlayer"):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        else:
            vc.pause()
            button.label, button.emoji = "Resume", "▶️"

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                embed=error_embed("Tidak ada lagu yang diputar."), ephemeral=True,
            )
        vc.stop()
        await interaction.response.send_message(
            embed=success_embed("⏭️ Lagu diskip."), ephemeral=True,
        )

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await vc.disconnect()
        players.pop(interaction.guild_id, None)
        await interaction.response.edit_message(
            embed=success_embed("👋 Playback dihentikan."),
            view=None,
        )

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.primary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = players.get(interaction.guild_id)
        upcoming = list(player.queue._queue) if player else []
        if not upcoming:
            return await interaction.response.send_message(
                embed=warning_embed("📭 Queue kosong."), ephemeral=True,
            )

        text = "\n".join(f"{i + 1}. {item.title}" for i, item in enumerate(upcoming[:10]))
        embed = discord.Embed(title="📜 Queue", description=text, color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Loop: Off", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    @discord.ui.button(label="Autoplay: Off", emoji="🔀", style=discord.ButtonStyle.secondary)
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        await interaction.response.edit_message(view=self)


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

        interaction.client.loop.create_task(self.player_loop())

    async def _send_error(self, error):
        logger.error("Player error: %s", error)
        err_str = str(error)
        if "403" in err_str or "Forbidden" in err_str:
            msg = "**Gagal memutar lagu** (403 Forbidden).\nSilahkan ulang pake `/play judul artis` ya."
        else:
            msg = f"**Error:** {err_str}\nSilahkan ulang pake `/play judul artis` ya."

        target = self.now_playing_message.channel if self.now_playing_message else self.interaction.channel
        try:
            await target.send(embed=error_embed(msg))
        except Exception:
            pass

    def _handle_next(self, error):
        if error:
            self.interaction.client.loop.create_task(self._send_error(error))
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
                self.current = None
                continue

            self.vc.play(
                source,
                after=lambda e: self.interaction.client.loop.call_soon_threadsafe(
                    self._handle_next, e,
                ),
            )

            await self._send_now_playing(source)

            await self.next.wait()
            source.cleanup()

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

    async def _autoplay_related(self):
        last_source = self._last_source
        if not last_source:
            return

        related_url = await get_related_video_url(last_source.data)
        if not related_url:
            logger.warning("Autoplay: no related videos found for '%s'", last_source.title)
            return

        try:
            source = await YTDLSource.from_url(
                related_url,
                loop=self.interaction.client.loop,
                stream=True,
            )
            source.requester = self.interaction.guild.me
            await self.queue.put(source)
            logger.info("Autoplay: enqueued '%s'", source.title)

            target = self.now_playing_message.channel if self.now_playing_message else self.interaction.channel
            await target.send(
                embed=info_embed(f"🔀 **Autoplay:** {source.title}")
            )
        except Exception as e:
            logger.error("Autoplay error for '%s': %s", related_url, e)

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
        if self.vc and self.vc.is_connected():
            await self.vc.disconnect()


players: dict[int, MusicPlayer] = {}


def get_player(interaction: discord.Interaction) -> MusicPlayer:
    if interaction.guild_id not in players:
        players[interaction.guild_id] = MusicPlayer(interaction)
    player = players[interaction.guild_id]
    player.vc = interaction.guild.voice_client
    return player
