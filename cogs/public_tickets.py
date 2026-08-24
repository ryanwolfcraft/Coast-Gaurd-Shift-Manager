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

        await channel.send(embed=embed, view=PublicTicketPanelView())
        await interaction.response.send_message(f"Public ticket panel posted in {channel.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PublicTicketCog(bot))
