import logging
import discord
from utils.logger import send_log_embed, format_datetime
from config import WELCOME_CHANNEL_ID, WELCOME_PROMPT
from commands.ai import ask_openrouter

logger = logging.getLogger("bot")


def register_member_events(client: discord.Client):
    @client.event
    async def on_member_join(member: discord.Member) -> None:
        # 1. Log member join
        # await send_log_embed(
        #     client=client,
        #     title="📥 MEMBER JOINED",
        #     color=discord.Color.green(),
        #     fields=[
        #         ("👤 User", member.mention, False),
        #         ("📅 Created At", format_datetime(member.created_at), True),
        #         ("🆔 ID", str(member.id), True),
        #     ],
        # )

        # 2. Auto Welcome Message with AI
        if WELCOME_CHANNEL_ID:
            channel = client.get_channel(WELCOME_CHANNEL_ID)
            if not channel:
                try:
                    channel = await client.fetch_channel(WELCOME_CHANNEL_ID)
                except Exception as e:
                    logger.error(f"Gagal mengambil channel welcome: {e}")
                    return

            if isinstance(channel, discord.TextChannel):
                prompt = WELCOME_PROMPT.format(name=member.display_name, mention=member.mention)
                try:
                    welcome_msg = await ask_openrouter(prompt)
                    await channel.send(welcome_msg)
                except Exception as e:
                    logger.error(f"Gagal mengirim welcome message AI: {e}")

    # @client.event
    # async def on_member_remove(member: discord.Member) -> None:
    #     await send_log_embed(
    #         client=client,
    #         title="📤 MEMBER LEFT",
    #         color=discord.Color.red(),
    #         fields=[
    #             ("👤 User", str(member), False),
    #             ("🆔 ID", str(member.id), True),
    #         ],
    #     )
    #
    # @client.event
    # async def on_member_update(before: discord.Member, after: discord.Member) -> None:
    #     if before.nick == after.nick:
    #         return
    #
    #     await send_log_embed(
    #         client=client,
    #         title="📝 NICKNAME UPDATED",
    #         color=discord.Color.orange(),
    #         fields=[
    #             ("👤 User", after.mention, False),
    #             ("📌 Before", before.nick or before.name, True),
    #             ("📌 After", after.nick or after.name, True),
    #         ],
    #     )