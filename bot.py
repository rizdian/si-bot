import logging
import asyncio
import time

import discord
from discord import app_commands

from config import TOKEN, LOG_CHANNEL_ID, GUILD_ID
from commands.general import register_general_commands
from commands.ai import register_ai_commands
from commands.music import register_music_commands
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
        register_ai_commands(self.tree, self)
        register_music_commands(self.tree, self)

        # Sync guild commands
        guild = discord.Object(id=GUILD_ID)
        synced = await self.tree.sync(guild=guild)
        logger.info("✅ Synced guild commands: %s", [cmd.name for cmd in synced])

        # Global sync (opsional, uncomment jika ingin global)
        # await self.tree.sync()
        # logger.info("✅ Synced global commands")

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
    
    max_retries = 5
    retry_delay = 5  # Start with 5 seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            client.run(TOKEN)
            break  # Exit loop if client runs successfully (though run() is blocking until logout)
        except (discord.errors.DiscordServerError, discord.errors.HTTPException) as e:
            if attempt < max_retries:
                logger.warning(f"⚠️ Discord server error (attempt {attempt}/{max_retries}): {e}")
                logger.info(f"🔄 Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"❌ Failed to login after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during startup: {e}")
            raise


if __name__ == "__main__":
    main()