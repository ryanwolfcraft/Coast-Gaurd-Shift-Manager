# Coast Guard Supreme — Employee Scheduling Bot

A Discord bot for drafting, editing, deleting, and applying employee shift
schedules, with automatic DM reminders, start/end shift buttons, and
escalation if a shift isn't started.

## Commands

- **/draftschedule** `user` `starting-time` `ending-time` `date` — drafts a
  new shift and puts it on the unapplied edit list.
- **/draftscheduleedit** `user` — pick one of that user's applied shifts
  from a dropdown, then edit its user, date, or time in a form. Goes on the
  unapplied edit list.
- **/deleteschedule** `user` — pick one of that user's applied shifts from a
  dropdown to delete. Goes on the unapplied edit list.
- **/applyedits** — applies every drafted create/edit/delete. Affected users
  are DMed about the change.

By default these commands require the **Manage Server** permission. Adjust
that under Server Settings → Integrations in Discord if you want a
different role to manage schedules.

## Automatic shift flow

For every applied shift:

1. **1 hour before** the shift starts, the bot DMs the employee a reminder.
2. **At the start time**, the bot DMs the employee a message with a
   **Start Shift** button.
3. If they don't press it within **5 minutes**, the bot DMs another
   reminder — and repeats every 5 minutes.
4. If it's still not started after **30 minutes**, the bot DMs
   `<@1011630185243742308>` (configurable) with the employee and shift
   details.
5. Reminders keep going for **30 more minutes** (60 minutes total from the
   scheduled start), then stop.
6. Once started, at the shift's **end time** the bot DMs the employee an
   **End Shift** button.

All of this is driven by a background loop that checks every 30 seconds, so
it keeps working even if commands aren't being used, and picks back up
correctly after a restart (button state is stored in the database, not in
memory).

## Setup

1. Create a bot application at the
   [Discord Developer Portal](https://discord.com/developers/applications).
   Under **Bot**, enable the **Server Members Intent**. Under
   **OAuth2 → URL Generator**, select the `bot` and `applications.commands`
   scopes, and at minimum the `Send Messages`, `Use Slash Commands`, and
   `Read Message History` bot permissions, then use the generated link to
   invite the bot to your server.
2. Copy `.env.example` to `.env` and fill in `DISCORD_TOKEN`. Set `GUILD_ID`
   to your server's ID while testing so slash commands sync instantly.
3. Install dependencies and run locally:

   ```bash
   pip install -r requirements.txt
   python bot.py
   ```

## Deploying on Railway

1. Push this repository to GitHub, then create a new Railway project from
   that repo (Railway auto-detects Python via `requirements.txt` /
   `railway.json`).
2. In Railway → Variables, set `DISCORD_TOKEN` (and optionally `GUILD_ID`,
   `TIMEZONE`, `ESCALATION_USER_ID`).
3. **Important — persistent storage:** this bot stores schedules in a local
   SQLite file (`scheduler.db`). Railway's filesystem is ephemeral across
   deploys/restarts by default, which would wipe your schedules. Add a
   [Railway Volume](https://docs.railway.app/reference/volumes) mounted at
   the project directory (or set `DB_PATH` to a path inside that volume) so
   the database survives redeploys.
4. Deploy. The `Procfile` (`worker: python bot.py`) tells Railway how to
   start the bot; since this is a background worker (not a web server), it
   doesn't need a public port.

## Notes / assumptions

- Times entered in commands are interpreted in the `TIMEZONE` you configure
  (default `America/New_York`). If an end time is earlier than the start
  time, the shift is treated as overnight (ending the next day).
- Editing a shift via `/draftscheduleedit` resets its reminder/start/end
  state, since the schedule itself changed.
- If two pending edits target the same original shift before `/applyedits`
  is run, they're applied in the order they were drafted.
