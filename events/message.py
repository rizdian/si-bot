import discord
from config import OWNER_USER_ID
from utils.logger import send_log_embed


def is_mentioned(message: discord.Message, user_id: int) -> bool:
    return any(user.id == user_id for user in message.mentions)


def register_message_events(client: discord.Client):

    # =========================
    # MESSAGE CREATE (AUTO RESPONSE)
    # =========================
    @client.event
    async def on_message(message: discord.Message) -> None:
        # ignore bot
        if message.author.bot:
            return

        # auto response jika owner di-tag
        if OWNER_USER_ID and is_mentioned(message, OWNER_USER_ID):
            await message.reply("Kenapa si Tag-tag")

        # WAJIB agar slash command tetap jalan
        await client.process_commands(message)

    # =========================
    # MESSAGE DELETE
    # =========================
    @client.event
    async def on_message_delete(message: discord.Message) -> None:
        if message.author.bot:
            return

        await send_log_embed(
            client=client,
            title="🗑 MESSAGE DELETED",
            color=discord.Color.red(),
            fields=[
                ("👤 Author", message.author.mention, False),
                ("📍 Channel", message.channel.mention, True),
                ("💬 Content", message.content or "[Empty/Embed]", False),
            ],
        )

    # =========================
    # MESSAGE EDIT
    # =========================
    @client.event
    async def on_message_edit(before: discord.Message, after: discord.Message) -> None:
        if before.author.bot:
            return

        if before.content == after.content:
            return

        await send_log_embed(
            client=client,
            title="✏ MESSAGE EDITED",
            color=discord.Color.blue(),
            fields=[
                ("👤 Author", before.author.mention, False),
                ("📍 Channel", before.channel.mention, True),
                ("📌 Before", before.content or "[Empty]", False),
                ("📌 After", after.content or "[Empty]", False),
            ],
        )