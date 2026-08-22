import asyncio

import discord

import config

TICKET_TYPES = {
    "cancelation": ("Cancelation Ticket", "cancelation"),
    "unavailability": ("Unavailability Ticket", "unavailability"),
    "question": ("General Ticket", "general"),
}

EMBED_COLOR = discord.Color(0x2C2F33)


def _has_staff_role(interaction: discord.Interaction) -> bool:
    role = interaction.guild.get_role(config.TICKET_STAFF_ROLE_ID)
    if role is None:
        return False
    return role in interaction.user.roles


class TicketPanelView(discord.ui.View):
    """Persistent panel with the ticket-type dropdown."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Select a ticket type",
        custom_id="ticket_panel_select",
        options=[
            discord.SelectOption(
                label="Cancelation Ticket",
                value="cancelation",
                description="Request to cancel a scheduled shift",
            ),
            discord.SelectOption(
                label="Unavailability Ticket",
                value="unavailability",
                description="Report that you are unavailable for scheduling",
            ),
            discord.SelectOption(
                label="Question Ticket",
                value="question",
                description="Ask staff a general question",
            ),
        ],
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await create_ticket(interaction, select.values[0])


async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    category = guild.get_channel(config.TICKET_CATEGORY_ID)
    if category is None:
        await interaction.response.send_message(
            "The ticket category could not be found. Please contact an administrator.",
            ephemeral=True,
        )
        return

    label, prefix = TICKET_TYPES[ticket_type]
    channel_name = f"{prefix}-{interaction.user.name}".lower().replace(" ", "-")

    existing = discord.utils.get(category.text_channels, name=channel_name)
    if existing:
        await interaction.response.send_message(
            f"You already have an open ticket: {existing.mention}", ephemeral=True
        )
        return

    await interaction.response.send_message("Creating your ticket...", ephemeral=True)

    staff_role = guild.get_role(config.TICKET_STAFF_ROLE_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True, read_message_history=True
        ),
    }
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    channel = await category.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        topic=f"{label} opened by {interaction.user} ({interaction.user.id})",
    )

    embed = discord.Embed(
        title=label,
        description="A new ticket has been opened. Please describe your request below.",
        color=EMBED_COLOR,
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="User", value=interaction.user.mention, inline=True)
    embed.add_field(name="User ID", value=str(interaction.user.id), inline=True)
    embed.add_field(name="Ticket Type", value=label, inline=True)
    embed.add_field(
        name="Account Created",
        value=discord.utils.format_dt(interaction.user.created_at, style="F"),
        inline=True,
    )
    embed.add_field(
        name="Joined Server",
        value=discord.utils.format_dt(interaction.user.joined_at, style="F")
        if interaction.user.joined_at
        else "Unknown",
        inline=True,
    )
    embed.set_footer(text="Use the buttons below to claim or close this ticket.")

    ping_content = staff_role.mention if staff_role else None
    await channel.send(content=ping_content, embed=embed, view=TicketControlView())

    await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    """Persistent Claim / Close buttons attached to each ticket's info embed."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_staff_role(interaction):
            await interaction.response.send_message(
                "You do not have permission to claim this ticket.", ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]
        for i, field in enumerate(embed.fields):
            if field.name == "Claimed By":
                embed.set_field_at(i, name="Claimed By", value=interaction.user.mention, inline=True)
                break
        else:
            embed.add_field(name="Claimed By", value=interaction.user.mention, inline=True)

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _has_staff_role(interaction):
            await interaction.response.send_message(
                "You do not have permission to close this ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"This ticket will be closed by {interaction.user.mention} in a few seconds."
        )
        try:
            await interaction.channel.edit(name=f"closed-{interaction.channel.name}"[:100])
        except discord.HTTPException:
            pass
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
