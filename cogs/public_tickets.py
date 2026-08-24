import discord
from discord import app_commands
from discord.ext import commands

from public_ticket_views import PublicTicketPanelView


class PublicTicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="sendpublicticketpanel",
        description="Post the public ticket panel (support, staff report, HR report) in a channel",
    )
    @app_commands.describe(channel="Channel to post the panel in")
    @app_commands.default_permissions(administrator=True)
    async def sendpublicticketpanel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        perms = channel.permissions_for(interaction.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await interaction.followup.send(
                f"I don't have permission to send messages/embeds in {channel.mention}. "
                f"Grant me `Send Messages` and `Embed Links` there and try again.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="Support Tickets",
            description=(
                "Select an option below to open a private ticket.\n\n"
                "**General Support** — General questions or help from staff.\n"
                "**Staff Report** — Report a concern about a staff member.\n"
                "**HR Report** — Report a matter for Human Resources. "
                "Visible only to Administrators.\n\n"
                "A private channel will be created and the relevant team will be notified."
            ),
            color=discord.Color(0x2C2F33),
        )
        embed.set_footer(text="Please only open one ticket at a time.")

        try:
            await channel.send(embed=embed, view=PublicTicketPanelView())
        except discord.Forbidden:
            await interaction.followup.send(
                f"I don't have permission to post in {channel.mention}.", ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to post the panel: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"Public ticket panel posted in {channel.mention}.", ephemeral=True)

    @sendpublicticketpanel.error
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        msg = f"Something went wrong: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PublicTicketCog(bot))
