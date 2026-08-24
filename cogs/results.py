import discord
from discord import app_commands
from discord.ext import commands

import config

STAFF_ROLE_ID = config.TICKET_STAFF_ROLE_ID


class ResultsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ----------------------------------------------------------------
    # /application-result
    # ----------------------------------------------------------------

    @app_commands.command(name="application-result", description="Post an application result and update roles")
    @app_commands.describe(user="The applicant", result="The application outcome", reason="Reason for the decision")
    @app_commands.choices(
        result=[
            app_commands.Choice(name="Accepted", value="accepted"),
            app_commands.Choice(name="Denied", value="denied"),
        ]
    )
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def application_result(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        result: app_commands.Choice[str],
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True)

        channel = interaction.guild.get_channel(config.APPLICATION_RESULT_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send("The application results channel could not be found.", ephemeral=True)
            return

        accepted = result.value == "accepted"
        color = discord.Color.green() if accepted else discord.Color.red()

        embed = discord.Embed(title="Application Result", color=color)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Applicant", value=user.mention, inline=True)
        embed.add_field(name="Result", value=result.name, inline=True)
        embed.add_field(name="Reviewed By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {user.id}")

        role_note = ""
        if accepted:
            roles_to_add = [interaction.guild.get_role(rid) for rid in config.APPLICATION_ACCEPTED_ROLE_IDS]
            roles_to_add = [r for r in roles_to_add if r is not None]
            try:
                if roles_to_add:
                    await user.add_roles(*roles_to_add, reason="Application accepted")
            except discord.Forbidden:
                role_note = "\n\nCould not assign roles — check my role position and permissions."

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                f"I don't have permission to post in {channel.mention}.", ephemeral=True
            )
            return

        await interaction.followup.send(f"Application result posted in {channel.mention}.{role_note}", ephemeral=True)

    # ----------------------------------------------------------------
    # /training-result
    # ----------------------------------------------------------------

    @app_commands.command(name="training-result", description="Post a training result and update roles")
    @app_commands.describe(user="The trainee", result="The training outcome", reason="Reason for the decision")
    @app_commands.choices(
        result=[
            app_commands.Choice(name="Passed", value="passed"),
            app_commands.Choice(name="Failed", value="failed"),
        ]
    )
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def training_result(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        result: app_commands.Choice[str],
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True)

        channel = interaction.guild.get_channel(config.TRAINING_RESULT_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send("The training results channel could not be found.", ephemeral=True)
            return

        passed = result.value == "passed"
        color = discord.Color.green() if passed else discord.Color.red()

        embed = discord.Embed(title="Training Result", color=color)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Trainee", value=user.mention, inline=True)
        embed.add_field(name="Result", value=result.name, inline=True)
        embed.add_field(name="Reviewed By", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {user.id}")

        role_note = ""
        if passed:
            remove_role = interaction.guild.get_role(config.TRAINING_REMOVE_ROLE_ID)
            add_roles = [interaction.guild.get_role(rid) for rid in config.TRAINING_PASSED_ROLE_IDS]
            add_roles = [r for r in add_roles if r is not None]
            try:
                if remove_role is not None:
                    await user.remove_roles(remove_role, reason="Training passed")
                if add_roles:
                    await user.add_roles(*add_roles, reason="Training passed")
            except discord.Forbidden:
                role_note = "\n\nCould not update roles — check my role position and permissions."

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            await interaction.followup.send(
                f"I don't have permission to post in {channel.mention}.", ephemeral=True
            )
            return

        await interaction.followup.send(f"Training result posted in {channel.mention}.{role_note}", ephemeral=True)

    @application_result.error
    @training_result.error
    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            msg = "You don't have permission to use this command."
        else:
            msg = f"Something went wrong: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ResultsCog(bot))
