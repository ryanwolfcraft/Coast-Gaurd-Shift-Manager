from datetime import datetime, timedelta, timezone

import discord

import time_utils
from database import get_db


# --------------------------------------------------------------------------
# Start / End shift buttons (persistent — survive bot restarts because the
# custom_id is deterministic and re-registered on startup, see bot.py)
# --------------------------------------------------------------------------

class StartShiftView(discord.ui.View):
    def __init__(self, schedule_id: int):
        super().__init__(timeout=None)
        self.schedule_id = schedule_id
        self.start_button.custom_id = f"start_shift:{schedule_id}"

    @discord.ui.button(label="Start Shift", style=discord.ButtonStyle.success)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_db()
        row = await (await db.execute(
            "SELECT * FROM schedules WHERE id=?", (self.schedule_id,)
        )).fetchone()

        if row is None or row["status"] != "applied":
            await interaction.response.send_message("This shift no longer exists.", ephemeral=True)
            return
        if row["started_at"]:
            await interaction.response.send_message("You've already started this shift.", ephemeral=True)
            return

        now = datetime.now(timezone.utc).isoformat()
        await db.execute("UPDATE schedules SET started_at=? WHERE id=?", (now, self.schedule_id))
        await db.commit()

        button.disabled = True
        button.label = "Shift Started ✅"
        await interaction.response.edit_message(view=self)


class EndShiftView(discord.ui.View):
    def __init__(self, schedule_id: int):
        super().__init__(timeout=None)
        self.schedule_id = schedule_id
        self.end_button.custom_id = f"end_shift:{schedule_id}"

    @discord.ui.button(label="End Shift", style=discord.ButtonStyle.danger)
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_db()
        row = await (await db.execute(
            "SELECT * FROM schedules WHERE id=?", (self.schedule_id,)
        )).fetchone()

        if row is None or row["status"] != "applied":
            await interaction.response.send_message("This shift no longer exists.", ephemeral=True)
            return
        if row["ended_at"]:
            await interaction.response.send_message("You've already ended this shift.", ephemeral=True)
            return

        now = datetime.now(timezone.utc).isoformat()
        await db.execute("UPDATE schedules SET ended_at=? WHERE id=?", (now, self.schedule_id))
        await db.commit()

        button.disabled = True
        button.label = "Shift Ended ✅"
        await interaction.response.edit_message(view=self)


# --------------------------------------------------------------------------
# Shift picker (used by /draftscheduleedit and /deleteschedule) + edit modal
# --------------------------------------------------------------------------

class EditShiftModal(discord.ui.Modal, title="Edit Shift"):
    def __init__(self, schedule_row):
        super().__init__()
        self.schedule_id = schedule_row["id"]

        start = datetime.fromisoformat(schedule_row["start_time"]).astimezone(time_utils.TZ)
        end = datetime.fromisoformat(schedule_row["end_time"]).astimezone(time_utils.TZ)

        self.user_input = discord.ui.TextInput(
            label="User ID or @mention", default=schedule_row["user_id"], required=True
        )
        self.date_input = discord.ui.TextInput(
            label="Date (e.g. 2025-01-30)", default=start.strftime("%Y-%m-%d"), required=True
        )
        self.start_input = discord.ui.TextInput(
            label="Start time (e.g. 9:00 AM)", default=start.strftime("%I:%M %p"), required=True
        )
        self.end_input = discord.ui.TextInput(
            label="End time (e.g. 5:00 PM)", default=end.strftime("%I:%M %p"), required=True
        )

        for item in (self.user_input, self.date_input, self.start_input, self.end_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            start_dt = time_utils.parse_datetime(self.date_input.value, self.start_input.value)
            end_dt = time_utils.parse_datetime(self.date_input.value, self.end_input.value)
        except Exception:
            await interaction.response.send_message(
                "Couldn't parse that date/time. Try formats like `2025-01-30` and `9:00 AM`.",
                ephemeral=True,
            )
            return

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # overnight shift

        user_id_raw = self.user_input.value.strip().lstrip("<@!").rstrip(">")
        if not user_id_raw.isdigit():
            await interaction.response.send_message("That doesn't look like a valid user ID or mention.", ephemeral=True)
            return

        db = get_db()
        await db.execute(
            "INSERT INTO pending_edits "
            "(action, schedule_id, user_id, start_time, end_time, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                "edit",
                self.schedule_id,
                user_id_raw,
                start_dt.isoformat(),
                end_dt.isoformat(),
                str(interaction.user.id),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()

        await interaction.response.send_message(
            f"Edit drafted for <@{user_id_raw}>: {time_utils.fmt(start_dt.isoformat())} → "
            f"{time_utils.fmt(end_dt.isoformat())}.\nUse `/applyedits` to apply it.",
            ephemeral=True,
        )


class ScheduleSelectView(discord.ui.View):
    """Dropdown of a user's currently-applied shifts. mode='edit' opens the
    edit modal on selection; mode='delete' immediately drafts a deletion."""

    def __init__(self, rows, mode: str, requester_id: int):
        super().__init__(timeout=180)
        self.mode = mode
        self.requester_id = requester_id

        options = []
        for row in rows[:25]:
            start = datetime.fromisoformat(row["start_time"]).astimezone(time_utils.TZ)
            end = datetime.fromisoformat(row["end_time"]).astimezone(time_utils.TZ)
            label = f"{start.strftime('%m/%d/%Y %I:%M %p')} - {end.strftime('%I:%M %p %Z')}"
            options.append(discord.SelectOption(label=label[:100], value=str(row["id"])))

        self.select = discord.ui.Select(placeholder="Choose a shift...", options=options)
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("This menu isn't for you.", ephemeral=True)
            return

        schedule_id = int(self.select.values[0])
        db = get_db()
        row = await (await db.execute("SELECT * FROM schedules WHERE id=?", (schedule_id,))).fetchone()
        if row is None or row["status"] != "applied":
            await interaction.response.send_message("That shift no longer exists.", ephemeral=True)
            return

        if self.mode == "edit":
            await interaction.response.send_modal(EditShiftModal(row))
        else:  # delete
            await db.execute(
                "INSERT INTO pending_edits "
                "(action, schedule_id, user_id, start_time, end_time, created_by, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    "delete",
                    schedule_id,
                    row["user_id"],
                    row["start_time"],
                    row["end_time"],
                    str(interaction.user.id),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            await db.commit()
            await interaction.response.send_message(
                f"Deletion drafted for the shift on {time_utils.fmt(row['start_time'])}.\n"
                f"Use `/applyedits` to apply it.",
                ephemeral=True,
            )
