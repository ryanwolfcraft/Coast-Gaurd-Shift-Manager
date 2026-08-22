import discord
from discord import app_commands
from discord.ext import commands

import config
from ticket_views import TicketPanelView


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="sendticketpanel",
        description="Post the ticket panel in the configured ticket channel",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def sendticketpanel(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(config.TICKET_PANEL_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                "The configured ticket panel channel could not be found.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Support Tickets",
            description=(
                "Select an option below to open a private ticket with staff.\n\n"
                "**Cancelation Ticket** — Request to cancel a scheduled shift.\n"
                "**Unavailability Ticket** — Report that you are unavailable for scheduling.\n"
                "**Question Ticket** — Ask staff a general question.\n\n"
                "A private channel will be created and staff will be notified."
            ),
            color=discord.Color(0x2C2F33),
        )
        embed.set_footer(text="Please only open one ticket at a time.")

        await channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(f"Ticket panel posted in {channel.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
