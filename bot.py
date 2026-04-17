import logging

import discord
from discord import app_commands

from config import TOKEN, LOG_CHANNEL_ID, GUILD_ID
from commands.general import register_general_commands
from events.member import register_member_events
from events.message import register_message_events
from utils.logger_setup import setup_logger


setup_logger()
logger = logging.getLogger("bot")


intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True


class MyClient(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        register_general_commands(self.tree, self)

        guild = discord.Object(id=GUILD_ID)
        synced = await self.tree.sync(guild=guild)

        logger.info("✅ Synced guild commands: %s", [cmd.name for cmd in synced])

client = MyClient()


@client.event
async def on_ready() -> None:
    logger.info("✅ Login sebagai %s", client.user)
    logger.info("📡 Log Channel ID: %s", LOG_CHANNEL_ID)
    logger.info("🏠 Guild ID: %s", GUILD_ID)


register_member_events(client)
register_message_events(client)


def main() -> None:
    if not TOKEN:
        logger.error("❌ DISCORD_TOKEN tidak ditemukan di .env")
        raise ValueError("❌ DISCORD_TOKEN tidak ditemukan di .env")

    logger.info("🚀 Starting bot...")
    client.run(TOKEN)


if __name__ == "__main__":
    main()