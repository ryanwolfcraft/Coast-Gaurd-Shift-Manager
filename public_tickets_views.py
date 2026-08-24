import asyncio

import discord

import config

STAFF_REPORT_ROLE_IDS = [
    1540102653365977160,
    1540102606813397092,
    1540102544045379685,
    1540102467738665020,
    1540102377095434341,
]

EMBED_COLOR = discord.Color(0x2C2F33)

# key -> (label, description, channel prefix, allowed_role_ids or None, admin_only)
PUBLIC_TICKET_TYPES = {
    "general_support": (
        "General Support",
        "General questions or help from staff",
        "support",
        STAFF_REPORT_ROLE_IDS,
        False,
    ),
    "staff_report": (
        "Staff Report",
        "Report a concern about a staff member",
        "staffreport",
        STAFF_REPORT_ROLE_IDS,
        False,
    ),
    "hr_report": (
        "HR Report",
        "Report a matter for Human Resources",
        "hrreport",
        None,
        True,
    ),
}


def _can_manage(interaction: discord.Interaction, allowed_role_ids, admin_only: bool) -> bool:
    if admin_only:
        return interaction.user.guild_permissions.administrator
    if interaction.user.guild_permissions.administrator:
        return True
    user_role_ids = {r.id for r in interaction.user.roles}
    return any(rid in user_role_ids for rid in (allowed_role_ids or []))


class PublicTicketPanelView(discord.ui.View):
    """Persistent panel with the public ticket-type dropdown."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Select a ticket type",
        custom_id="public_ticket_panel_select",
        options=[
            discord.SelectOption(
                label="General Support",
                value="general_support",
                description="General questions or help from staff",
            ),
            discord.SelectOption(
                label="Staff Report",
                value="staff_report",
                description="Report a concern about a staff member",
            ),
            discord.SelectOption(
                label="HR Report",
                value="hr_report",
                description="Report a matter for Human Resources",
            ),
        ],
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await create_public_ticket(interaction, select.values[0])


async def create_public_ticket(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    category = guild.get_channel(config.TICKET_CATEGORY_ID)
    if category is None:
        await interaction.response.send_message(
            "The ticket category could not be found. Please contact an administrator.",
            ephemeral=True,
        )
        return

    label, description, prefix, allowed_role_ids, admin_only = PUBLIC_TICKET_TYPES[ticket_type]
    channel_name = f"{prefix}-{interaction.user.name}".lower().replace(" ", "-")

    existing = discord.utils.get(category.text_channels, name=channel_name)
    if existing:
        await interaction.response.send_message(
            f"You already have an open ticket: {existing.mention}", ephemeral=True
        )
        return

    await interaction.response.send_message("Creating your ticket...", ephemeral=True)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True, read_message_history=True
        ),
    }

    ping_content = None
    if admin_only:
        # Administrator permission bypasses channel overwrites entirely, so
        # admins can already see this channel without an explicit overwrite.
        ping_content = None
    else:
        for role_id in allowed_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )
        mentions = [guild.get_role(rid).mention for rid in allowed_role_ids if guild.get_role(rid)]
        ping_content = " ".join(mentions) if mentions else None

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
    if admin_only:
        embed.set_footer(text="This ticket is only visible to Administrators.")
    else:
        embed.set_footer(text="Use the buttons below to claim or close this ticket.")

    await channel.send(
        content=ping_content,
        embed=embed,
        view=PublicTicketControlView(ticket_type),
    )

    await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)


class PublicTicketControlView(discord.ui.View):
    """Persistent Claim / Close buttons. Permission depends on ticket_type:
    general_support / staff_report -> any of STAFF_REPORT_ROLE_IDS,
    hr_report -> Administrator permission only."""

    def __init__(self, ticket_type: str):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        _, _, _, allowed_role_ids, admin_only = PUBLIC_TICKET_TYPES[ticket_type]
        self.allowed_role_ids = allowed_role_ids
        self.admin_only = admin_only
        self.claim_button.custom_id = f"public_ticket_claim:{ticket_type}"
        self.close_button.custom_id = f"public_ticket_close:{ticket_type}"

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _can_manage(interaction, self.allowed_role_ids, self.admin_only):
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

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not _can_manage(interaction, self.allowed_role_ids, self.admin_only):
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


ALL_PUBLIC_TICKET_TYPE_KEYS = list(PUBLIC_TICKET_TYPES.keys())
