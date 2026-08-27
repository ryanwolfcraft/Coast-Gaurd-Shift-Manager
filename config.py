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

TICKET_PANEL_CHANNEL_ID = int(os.getenv("TICKET_PANEL_CHANNEL_ID", "1540848281834356777"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "1540848250767024260"))
PUBLIC_TICKET_CATEGORY_ID = int(os.getenv("PUBLIC_TICKET_CATEGORY_ID", "1542626939465113721"))
TICKET_STAFF_ROLE_ID = int(os.getenv("TICKET_STAFF_ROLE_ID", "1540422846902173716"))

APPLICATION_RESULT_CHANNEL_ID = int(os.getenv("APPLICATION_RESULT_CHANNEL_ID", "1540427781677121686"))
APPLICATION_ACCEPTED_ROLE_IDS = [1540408778607034378, 1540104435227820092]

TRAINING_RESULT_CHANNEL_ID = int(os.getenv("TRAINING_RESULT_CHANNEL_ID", "1540760856139403304"))
TRAINING_REMOVE_ROLE_ID = 1540104435227820092
TRAINING_PASSED_ROLE_IDS = [1540408674466668574, 1540408034390450207, 1540104405829812406]
