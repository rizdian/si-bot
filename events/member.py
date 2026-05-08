import logging
import discord
from utils.logger import send_log_embed, format_datetime
from config import WELCOME_CHANNEL_ID, WELCOME_PROMPT, ROLE_BOYS_ID, ROLE_GIRLS_ID, EMOJI_BOY, EMOJI_GIRL
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
                    msg = await channel.send(welcome_msg)
                    
                    # Tambah reaction
                    await msg.add_reaction(EMOJI_BOY)
                    await msg.add_reaction(EMOJI_GIRL)
                except Exception as e:
                    logger.error(f"Gagal mengirim welcome message AI: {e}")

    @client.event
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
        # Cek apakah ini di welcome channel
        if payload.channel_id != WELCOME_CHANNEL_ID:
            return

        # Jangan proses reaction dari bot
        if payload.user_id == client.user.id:
            return

        channel = client.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        # Cek apakah message ini adalah welcome message (ada mention member)
        # Sesuai requirement: "hanya dia yang bisa reaction"
        # Kita cek apakah user yang reaction adalah user yang di-mention di message
        if not any(mention.id == payload.user_id for mention in message.mentions):
            # Jika bukan dia yang di-mention, hapus reaction-nya
            try:
                await message.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
            except Exception:
                pass
            return

        # Jika sudah sampai sini, berarti user yang reaction adalah user yang benar
        guild = client.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member
        if not member:
            return

        role_id = None
        if str(payload.emoji) == EMOJI_BOY:
            role_id = ROLE_BOYS_ID
        elif str(payload.emoji) == EMOJI_GIRL:
            role_id = ROLE_GIRLS_ID

        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                    logger.info(f"Berhasil memberikan role {role.name} ke {member.display_name}")
                except Exception as e:
                    logger.error(f"Gagal memberikan role: {e}")

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