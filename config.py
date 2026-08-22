import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Optional: set this to your server's ID during development to make
# slash commands sync instantly to that guild instead of globally
# (global sync can take up to an hour to propagate).
GUILD_ID = os.getenv("GUILD_ID")

# IANA timezone name used to interpret dates/times typed into commands.
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

# User that gets DMed when someone misses the 30-minute mark without
# starting their shift.
ESCALATION_USER_ID = int(os.getenv("ESCALATION_USER_ID", "1011630185243742308"))

DB_PATH = os.getenv("DB_PATH", "scheduler.db")
