import discord
from utils.logger import send_log_embed, format_datetime


def register_member_events(client: discord.Client):
    @client.event
    async def on_member_join(member: discord.Member) -> None:
        await send_log_embed(
            client=client,
            title="📥 MEMBER JOINED",
            color=discord.Color.green(),
            fields=[
                ("👤 User", member.mention, False),
                ("📅 Created At", format_datetime(member.created_at), True),
                ("🆔 ID", str(member.id), True),
            ],
        )

    @client.event
    async def on_member_remove(member: discord.Member) -> None:
        await send_log_embed(
            client=client,
            title="📤 MEMBER LEFT",
            color=discord.Color.red(),
            fields=[
                ("👤 User", str(member), False),
                ("🆔 ID", str(member.id), True),
            ],
        )

    @client.event
    async def on_member_update(before: discord.Member, after: discord.Member) -> None:
        if before.nick == after.nick:
            return

        await send_log_embed(
            client=client,
            title="📝 NICKNAME UPDATED",
            color=discord.Color.orange(),
            fields=[
                ("👤 User", after.mention, False),
                ("📌 Before", before.nick or before.name, True),
                ("📌 After", after.nick or after.name, True),
            ],
        )