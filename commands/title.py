import discord
from discord import app_commands, ui
import re

from config import GUILD_ID, TITLE_CHANNEL_ID
from utils.logger import now_utc

TEST_GUILD = discord.Object(id=GUILD_ID)

# Pattern to match [title] name
TITLE_PATTERN = re.compile(r"^\[(.*?)\] (.*)$")

def _get_original_name(member: discord.Member) -> str:
    """Extract original name from nickname if it has a title."""
    current_nick = member.nick if member.nick else member.global_name or member.name
    match = TITLE_PATTERN.match(current_nick)
    if match:
        return match.group(2).strip()
    return current_nick

class TitleModal(ui.Modal, title="Set Your Title"):
    title_input = ui.TextInput(
        label="Title",
        placeholder="Misal: IDNS",
        min_length=1,
        max_length=20,
    )

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Command ini cuma bisa di server.", ephemeral=True)
            return

        original_name = _get_original_name(member)
        new_nick = f"[{self.title_input.value}] {original_name}"

        if len(new_nick) > 15:
            await interaction.response.send_message(
                "❌ Kepanjangan njer, maksimal 15 karakter termasuk nama lu.",
                ephemeral=True
            )
            return

        try:
            await member.edit(nick=new_nick)
            await interaction.response.send_message(f"✅ Title berhasil dipasang! Nickname lu jadi: **{new_nick}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Gue gak punya izin buat ganti nickname lu.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ada error: {e}", ephemeral=True)

class TitleView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Set Title", style=discord.ButtonStyle.green, custom_id="set_title_btn")
    async def set_title(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.channel_id != TITLE_CHANNEL_ID:
            await interaction.response.send_message(f"❌ Pake di <#{TITLE_CHANNEL_ID}> dong.", ephemeral=True)
            return
        await interaction.response.send_modal(TitleModal())

    @ui.button(label="Remove Title", style=discord.ButtonStyle.red, custom_id="remove_title_btn")
    async def remove_title(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.channel_id != TITLE_CHANNEL_ID:
            await interaction.response.send_message(f"❌ Pake di <#{TITLE_CHANNEL_ID}> dong.", ephemeral=True)
            return
            
        member = interaction.user
        if not isinstance(member, discord.Member):
            return

        original_name = _get_original_name(member)
        
        try:
            # Jika original_name sama dengan nama asli, hapus nick (set ke None)
            target_nick = None if original_name == (member.global_name or member.name) else original_name
            await member.edit(nick=target_nick)
            await interaction.response.send_message(f"🗑️ Title dihapus. Balik ke: **{original_name}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Gue gak punya izin buat ganti nickname lu.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ada error: {e}", ephemeral=True)

def register_title_commands(tree: app_commands.CommandTree, client: discord.Client):
    @tree.command(name="setup_title", description="Kirim panel setting title ke channel ini", guild=TEST_GUILD)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_title(interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🏷️ Setting Title Nickname",
            description=(
                "Klik tombol di bawah buat pasang atau hapus title di depan nama lu.\n\n"
                "**Format:** `[TITLE] Nama Lu Sekarang`"
            ),
            color=discord.Color.blue(),
            timestamp=now_utc()
        )
        embed.set_footer(text="System Title Management")
        
        await interaction.response.send_message("Panel dikirim!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=TitleView())

    # Menambahkan error handler buat setup_title
    @setup_title.error
    async def setup_title_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Cuma admin yang bisa setup ginian.", ephemeral=True)
