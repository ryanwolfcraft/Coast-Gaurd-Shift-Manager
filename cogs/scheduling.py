from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import time_utils
from database import get_db
from views import EndShiftView, ScheduleSelectView, StartShiftView

REMINDER_INTERVAL_SECONDS = 300      # 5 minutes between "you haven't started" DMs
ESCALATION_AFTER_SECONDS = 1800      # 30 minutes -> DM the escalation user
STOP_AFTER_SECONDS = 3600            # 30 more minutes of reminders, then stop (60 min total)


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    async def _dm_user(self, user_id: str, content: str = None, view: discord.ui.View = None):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await user.send(content=content, view=view)
        except Exception:
            pass

    # ----------------------------------------------------------------
    # /draftschedule
    # ----------------------------------------------------------------

    @app_commands.command(name="draftschedule", description="Draft a new shift for a user")
    @app_commands.describe(
        user="User to schedule",
        starting_time="Start time, e.g. 9:00 AM",
        ending_time="End time, e.g. 5:00 PM",
        date="Date, e.g. 2025-01-30",
    )
    @app_commands.rename(starting_time="starting-time", ending_time="ending-time")
    @app_commands.default_permissions(manage_guild=True)
    async def draftschedule(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        starting_time: str,
        ending_time: str,
        date: str,
    ):
        try:
            start_dt = time_utils.parse_datetime(date, starting_time)
            end_dt = time_utils.parse_datetime(date, ending_time)
        except Exception:
            await interaction.response.send_message(
                "Couldn't parse that date/time. Try formats like `2025-01-30` and `9:00 AM`.",
                ephemeral=True,
            )
            return

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # overnight shift

        db = get_db()
        await db.execute(
            "INSERT INTO pending_edits "
            "(action, schedule_id, user_id, start_time, end_time, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                "create",
                None,
                str(user.id),
                start_dt.isoformat(),
                end_dt.isoformat(),
                str(interaction.user.id),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()

        await interaction.response.send_message(
            f"Draft created for {user.mention}: **{time_utils.fmt(start_dt.isoformat())}** → "
            f"**{time_utils.fmt(end_dt.isoformat())}**.\nUse `/applyedits` to apply it.",
            ephemeral=True,
        )

    # ----------------------------------------------------------------
    # /draftscheduleedit
    # ----------------------------------------------------------------

    @app_commands.command(name="draftscheduleedit", description="Edit one of a user's existing applied shifts")
    @app_commands.describe(user="User whose schedule to edit")
    @app_commands.default_permissions(manage_guild=True)
    async def draftscheduleedit(self, interaction: discord.Interaction, user: discord.Member):
        db = get_db()
        cur = await db.execute(
            "SELECT * FROM schedules WHERE user_id=? AND status='applied' ORDER BY start_time",
            (str(user.id),),
        )
        rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message(f"{user.mention} has no applied shifts.", ephemeral=True)
            return

        view = ScheduleSelectView(rows, mode="edit", requester_id=interaction.user.id)
        await interaction.response.send_message(
            f"Select the shift to edit for {user.mention}:", view=view, ephemeral=True
        )

    # ----------------------------------------------------------------
    # /deleteschedule
    # ----------------------------------------------------------------

    @app_commands.command(name="deleteschedule", description="Delete one of a user's existing applied shifts")
    @app_commands.describe(user="User whose schedule to delete")
    @app_commands.default_permissions(manage_guild=True)
    async def deleteschedule(self, interaction: discord.Interaction, user: discord.Member):
        db = get_db()
        cur = await db.execute(
            "SELECT * FROM schedules WHERE user_id=? AND status='applied' ORDER BY start_time",
            (str(user.id),),
        )
        rows = await cur.fetchall()
        if not rows:
            await interaction.response.send_message(f"{user.mention} has no applied shifts.", ephemeral=True)
            return

        view = ScheduleSelectView(rows, mode="delete", requester_id=interaction.user.id)
        await interaction.response.send_message(
            f"Select the shift to delete for {user.mention}:", view=view, ephemeral=True
        )

    # ----------------------------------------------------------------
    # /applyedits
    # ----------------------------------------------------------------

    @app_commands.command(name="applyedits", description="Apply all drafted schedule edits")
    @app_commands.default_permissions(manage_guild=True)
    async def applyedits(self, interaction: discord.Interaction):
        db = get_db()
        cur = await db.execute("SELECT * FROM pending_edits ORDER BY id")
        edits = await cur.fetchall()

        if not edits:
            await interaction.response.send_message("There are no pending edits.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        applied_count = 0

        for e in edits:
            if e["action"] == "create":
                cur2 = await db.execute(
                    "INSERT INTO schedules (user_id, start_time, end_time, status, created_at) "
                    "VALUES (?,?,?,?,?)",
                    (e["user_id"], e["start_time"], e["end_time"], "applied", datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()
                await self._dm_user(
                    e["user_id"],
                    f"📅 A new shift has been scheduled for you:\n"
                    f"**{time_utils.fmt(e['start_time'])}** → **{time_utils.fmt(e['end_time'])}**",
                )

            elif e["action"] == "edit":
                old = await (await db.execute(
                    "SELECT * FROM schedules WHERE id=?", (e["schedule_id"],)
                )).fetchone()
                if old is None:
                    continue

                await db.execute(
                    "UPDATE schedules SET user_id=?, start_time=?, end_time=?, status='applied', "
                    "reminder_hour_sent=0, start_prompt_sent=0, start_prompt_sent_at=NULL, "
                    "last_start_reminder_at=NULL, escalation_sent=0, reminders_stopped=0, "
                    "started_at=NULL, end_prompt_sent=0, ended_at=NULL WHERE id=?",
                    (e["user_id"], e["start_time"], e["end_time"], e["schedule_id"]),
                )
                await db.commit()

                await self._dm_user(
                    e["user_id"],
                    f"✏️ Your shift has been updated:\n"
                    f"**{time_utils.fmt(e['start_time'])}** → **{time_utils.fmt(e['end_time'])}**",
                )
                if old["user_id"] != e["user_id"]:
                    await self._dm_user(
                        old["user_id"],
                        f"Your shift on **{time_utils.fmt(old['start_time'])}** has been reassigned "
                        f"to another team member.",
                    )

            elif e["action"] == "delete":
                old = await (await db.execute(
                    "SELECT * FROM schedules WHERE id=?", (e["schedule_id"],)
                )).fetchone()
                if old is None:
                    continue

                await db.execute("UPDATE schedules SET status='deleted' WHERE id=?", (e["schedule_id"],))
                await db.commit()

                await self._dm_user(
                    old["user_id"],
                    f"🗑️ Your shift on **{time_utils.fmt(old['start_time'])}** has been cancelled.",
                )

            applied_count += 1

        await db.execute("DELETE FROM pending_edits")
        await db.commit()

        await interaction.followup.send(f"Applied {applied_count} edit(s).", ephemeral=True)
            # ----------------------------------------------------------------
    # /schedules
    # ----------------------------------------------------------------

    @app_commands.command(name="schedules", description="View upcoming applied schedules")
    @app_commands.describe(user="Optional: only show this user's schedule")
    @app_commands.default_permissions(manage_guild=True)
    async def schedules(self, interaction: discord.Interaction, user: discord.Member = None):
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()

        if user is not None:
            cur = await db.execute(
                "SELECT * FROM schedules WHERE status='applied' AND user_id=? AND end_time >= ? "
                "ORDER BY start_time",
                (str(user.id), now),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM schedules WHERE status='applied' AND end_time >= ? ORDER BY start_time",
                (now,),
            )
        rows = await cur.fetchall()

        title = f"Schedule — {user.display_name}" if user else "Schedule — All Staff"
        embed = discord.Embed(title=title, color=discord.Color(0x2C2F33))

        if not rows:
            embed.description = "There are no upcoming shifts."
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        lines = []
        for row in rows[:25]:
            status_bits = []
            if row["started_at"] and not row["ended_at"]:
                status_bits.append("in progress")
            elif row["ended_at"]:
                status_bits.append("completed")
            status = f" *({', '.join(status_bits)})*" if status_bits else ""

            prefix = "" if user else f"<@{row['user_id']}> — "
            lines.append(
                f"{prefix}**{time_utils.fmt(row['start_time'])}** → "
                f"**{time_utils.fmt(row['end_time'])}**{status}"
            )

        # Discord embed descriptions cap at 4096 chars; fields cap at 1024,
        # so chunk into fields of a handful of lines each to stay safe.
        chunk = []
        chunk_len = 0
        field_index = 1
        for line in lines:
            if chunk_len + len(line) + 1 > 1000:
                embed.add_field(name="\u200b" if field_index > 1 else "Upcoming Shifts", value="\n".join(chunk), inline=False)
                chunk, chunk_len = [], 0
                field_index += 1
            chunk.append(line)
            chunk_len += len(line) + 1
        if chunk:
            embed.add_field(name="\u200b" if field_index > 1 else "Upcoming Shifts", value="\n".join(chunk), inline=False)

        if len(rows) > 25:
            embed.set_footer(text=f"Showing 25 of {len(rows)} upcoming shifts.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    

    # ----------------------------------------------------------------
    # Background loop: reminders, start/end prompts, escalation
    # ----------------------------------------------------------------

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        db = get_db()
        now = datetime.now(timezone.utc)

        cur = await db.execute("SELECT * FROM schedules WHERE status='applied'")
        rows = await cur.fetchall()

        for row in rows:
            start = datetime.fromisoformat(row["start_time"])
            end = datetime.fromisoformat(row["end_time"])

            # 1) One-hour-before reminder
            if not row["reminder_hour_sent"] and start - timedelta(hours=1) <= now < start:
                await self._dm_user(
                    row["user_id"],
                    f"⏰ Reminder: your shift starts in about 1 hour, at "
                    f"**{time_utils.fmt(row['start_time'])}**.",
                )
                await db.execute("UPDATE schedules SET reminder_hour_sent=1 WHERE id=?", (row["id"],))
                await db.commit()

            # 2) Start-of-shift prompt with a Start button
            if not row["start_prompt_sent"] and now >= start:
                view = StartShiftView(row["id"])
                self.bot.add_view(view)
                await self._dm_user(
                    row["user_id"],
                    f"🟢 Your shift is starting now (**{time_utils.fmt(row['start_time'])}**). "
                    f"Press the button below to start it.",
                    view=view,
                )
                await db.execute(
                    "UPDATE schedules SET start_prompt_sent=1, start_prompt_sent_at=?, "
                    "last_start_reminder_at=? WHERE id=?",
                    (now.isoformat(), now.isoformat(), row["id"]),
                )
                await db.commit()
                continue

            # 3) Follow-up reminders / escalation while shift is un-started
            if row["start_prompt_sent"] and not row["started_at"] and not row["reminders_stopped"]:
                prompt_at = datetime.fromisoformat(row["start_prompt_sent_at"])
                elapsed = (now - prompt_at).total_seconds()

                if elapsed >= STOP_AFTER_SECONDS:
                    await db.execute("UPDATE schedules SET reminders_stopped=1 WHERE id=?", (row["id"],))
                    await db.commit()
                    continue

                last_reminder = datetime.fromisoformat(row["last_start_reminder_at"])
                since_last = (now - last_reminder).total_seconds()
                if since_last >= REMINDER_INTERVAL_SECONDS:
                    await self._dm_user(
                        row["user_id"],
                        f"🔔 Reminder: you still haven't started your shift "
                        f"(**{time_utils.fmt(row['start_time'])}**). Please press Start when ready.",
                    )
                    await db.execute(
                        "UPDATE schedules SET last_start_reminder_at=? WHERE id=?",
                        (now.isoformat(), row["id"]),
                    )
                    await db.commit()

                if elapsed >= ESCALATION_AFTER_SECONDS and not row["escalation_sent"]:
                    try:
                        user_obj = await self.bot.fetch_user(int(row["user_id"]))
                        user_label = str(user_obj)
                    except Exception:
                        user_label = row["user_id"]
                    await self._dm_user(
                        str(config.ESCALATION_USER_ID),
                        f"🚨 <@{row['user_id']}> ({user_label}) has not started their shift.\n"
                        f"Scheduled start: **{time_utils.fmt(row['start_time'])}**\n"
                        f"Schedule ID: {row['id']}",
                    )
                    await db.execute("UPDATE schedules SET escalation_sent=1 WHERE id=?", (row["id"],))
                    await db.commit()

            # 4) End-of-shift prompt with an End button (only once the shift was actually started)
            if row["started_at"] and not row["ended_at"] and not row["end_prompt_sent"] and now >= end:
                view = EndShiftView(row["id"])
                self.bot.add_view(view)
                await self._dm_user(
                    row["user_id"],
                    f"🔴 Your shift is scheduled to end now (**{time_utils.fmt(row['end_time'])}**). "
                    f"Press the button below to end it.",
                    view=view,
                )
                await db.execute("UPDATE schedules SET end_prompt_sent=1 WHERE id=?", (row["id"],))
                await db.commit()

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    @draftschedule.error
    @draftscheduleedit.error
    @deleteschedule.error
    @applyedits.error
    @schedules.error
    async def on_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
    async def on_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "You don't have permission to use this command."
        else:
            msg = f"Something went wrong: {error}"
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ScheduleCog(bot))
