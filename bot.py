import discord
from discord import app_commands
from dotenv import load_dotenv
import os
import datetime

# load env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ===== CONFIG =====
LOG_CHANNEL_ID_STR = os.getenv("LOG_CHANNEL_ID")
try:
    LOG_CHANNEL_ID = int(LOG_CHANNEL_ID_STR) if LOG_CHANNEL_ID_STR else None
except ValueError:
    LOG_CHANNEL_ID = None
    print("❌ LOG_CHANNEL_ID di .env bukan angka valid!")

# ===== INTENTS =====
intents = discord.Intents.default()
intents.members = True  # WAJIB untuk detect perubahan member
intents.message_content = True # WAJIB untuk detect isi pesan

# ===== CLIENT =====
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MyClient()

# ===== READY =====
@client.event
async def on_ready():
    print(f"Login sebagai {client.user}")
    print(f"Log Channel ID: {LOG_CHANNEL_ID}")

# ===== HELPERS =====
async def send_log_embed(title, description=None, color=discord.Color.blue(), fields=None):
    if not LOG_CHANNEL_ID:
        print("❌ LOG_CHANNEL_ID not set!")
        return

    channel = client.get_channel(LOG_CHANNEL_ID)
    if not channel:
        print(f"❌ Channel log (ID: {LOG_CHANNEL_ID}) tidak ditemukan!")
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now()
    )

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    embed.set_footer(text=f"SI BOT • {datetime.datetime.now().strftime('%H:%M:%S')}")
    await channel.send(embed=embed)

# ===== SLASH COMMAND: /ping =====
@client.tree.command(name="ping", description="Cek bot hidup")
async def ping(interaction: discord.Interaction):
    latency = round(client.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! ({latency}ms)")

# ===== SLASH COMMAND: /serverinfo =====
@client.tree.command(name="serverinfo", description="Melihat informasi server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Command ini hanya bisa digunakan di server!", ephemeral=True)
        return

    embed = discord.Embed(title=f"🏰 {guild.name}", color=discord.Color.blue())
    embed.add_field(name="🆔 ID Server", value=guild.id, inline=True)
    embed.add_field(name="👑 Owner", value=guild.owner, inline=True)
    embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
    embed.add_field(name="📅 Created At", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=embed)

# ===== SLASH COMMAND: /userinfo =====
@client.tree.command(name="userinfo", description="Melihat informasi user")
@app_commands.describe(member="Member yang ingin dilihat (kosongkan untuk diri sendiri)")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    
    embed = discord.Embed(title=f"👤 {member.name}", color=member.color)
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📅 Joined At", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="📅 Created At", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="🏷 Roles", value=", ".join([role.mention for role in member.roles[1:]]) or "No roles", inline=False)
    
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    await interaction.response.send_message(embed=embed)

# ===== SLASH COMMAND: /log =====
@client.tree.command(name="log", description="Test log manual")
async def log(interaction: discord.Interaction):
    fields = [
        ("👤 User", interaction.user.mention, False),
        ("📌 Event", "Manual Trigger", False)
    ]
    
    await send_log_embed(
        title="📡 TRACE LOG",
        color=discord.Color.green(),
        fields=fields
    )
    
    await interaction.response.send_message("✅ Log sent to log channel!", ephemeral=True)

# ===== AUTO LOGS =====

# MEMBER JOINED
@client.event
async def on_member_join(member: discord.Member):
    fields = [
        ("👤 User", member.mention, False),
        ("📅 Created At", member.created_at.strftime("%Y-%m-%d"), True),
        ("🆔 ID", member.id, True)
    ]
    await send_log_embed(
        title="📥 MEMBER JOINED",
        color=discord.Color.green(),
        fields=fields
    )

# MEMBER REMOVED
@client.event
async def on_member_remove(member: discord.Member):
    fields = [
        ("👤 User", str(member), False),
        ("🆔 ID", member.id, True)
    ]
    await send_log_embed(
        title="📤 MEMBER LEFT",
        color=discord.Color.red(),
        fields=fields
    )

# NICKNAME CHANGE
@client.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.nick != after.nick:
        fields = [
            ("👤 User", after.mention, False),
            ("📌 Before", before.nick or before.name, True),
            ("📌 After", after.nick or after.name, True)
        ]
        await send_log_embed(
            title="📝 NICKNAME UPDATED",
            color=discord.Color.orange(),
            fields=fields
        )

# MESSAGE DELETED
@client.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return

    fields = [
        ("👤 Author", message.author.mention, False),
        ("📍 Channel", message.channel.mention, True),
        ("💬 Content", message.content or "[Empty/Embed]", False)
    ]
    await send_log_embed(
        title="🗑 MESSAGE DELETED",
        color=discord.Color.red(),
        fields=fields
    )

# MESSAGE EDITED
@client.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or before.content == after.content:
        return

    fields = [
        ("👤 Author", before.author.mention, False),
        ("📍 Channel", before.channel.mention, True),
        ("📌 Before", before.content, False),
        ("📌 After", after.content, False)
    ]
    await send_log_embed(
        title="✏ MESSAGE EDITED",
        color=discord.Color.blue(),
        fields=fields
    )

# ===== RUN =====
if not TOKEN:
    raise ValueError("❌ DISCORD_TOKEN tidak ditemukan di .env")

client.run(TOKEN)