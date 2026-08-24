import discord
from discord.ext import commands

import config
from database import get_db, init_db
from views import EndShiftView, StartShiftView
from ticket_views import TicketControlView, TicketPanelView
from public_ticket_views import PublicTicketPanelView, PublicTicketControlView, ALL_PUBLIC_TICKET_TYPE_KEYS

intents = discord.Intents.default()
intents.members = True  # needed to resolve Members from user IDs / DM them


class SchedulerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()
        await self.load_extension("cogs.scheduling")
        await self.load_extension("cogs.tickets")
        await self.load_extension("cogs.public_tickets")
        await self.load_extension("cogs.results")
        await self._register_persistent_views()
        await self._sync_commands()

    async def _sync_commands(self):
        try:
            if config.GUILD_ID:
                guild = discord.Object(id=int(config.GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"Synced commands to guild {config.GUILD_ID}")
            else:
                await self.tree.sync()
                print("Synced commands globally")
        except discord.Forbidden:
            print(
                "WARNING: Command sync failed with 403 Missing Access. "
                "Re-invite the bot with an OAuth2 URL that includes BOTH the 'bot' "
                "and 'applications.commands' scopes, and confirm GUILD_ID is correct."
            )
        except Exception as e:
            print(f"WARNING: Command sync failed: {e}")

    async def _register_persistent_views(self):
        db = get_db()

        cur = await db.execute(
            "SELECT id FROM schedules WHERE status='applied' AND start_prompt_sent=1 "
            "AND started_at IS NULL AND reminders_stopped=0"
        )
        for row in await cur.fetchall():
            self.add_view(StartShiftView(row["id"]))

        cur = await db.execute(
            "SELECT id FROM schedules WHERE status='applied' AND end_prompt_sent=1 AND ended_at IS NULL"
        )
        for row in await cur.fetchall():
            self.add_view(EndShiftView(row["id"]))

        self.add_view(TicketPanelView())
        self.add_view(TicketControlView())

        self.add_view(PublicTicketPanelView())
        for ticket_type in ALL_PUBLIC_TICKET_TYPE_KEYS:
            self.add_view(PublicTicketControlView(ticket_type))


bot = SchedulerBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")


def main():
    if not config.DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set. Add it to your .env or Railway variables.")
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
