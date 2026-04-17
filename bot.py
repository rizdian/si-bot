import discord
from discord import app_commands

from config import TOKEN, LOG_CHANNEL_ID
from commands.general import register_general_commands
from events.member import register_member_events
from events.message import register_message_events


intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        register_general_commands(self.tree, self)
        await self.tree.sync()


client = MyClient()


@client.event
async def on_ready():
    print(f"✅ Login sebagai {client.user}")
    print(f"📡 Log Channel ID: {LOG_CHANNEL_ID}")


register_member_events(client)
register_message_events(client)


def main():
    if not TOKEN:
        raise ValueError("❌ DISCORD_TOKEN tidak ditemukan di .env")

    client.run(TOKEN)


if __name__ == "__main__":
    main()