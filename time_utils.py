from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as dateparser

import config

TZ = ZoneInfo(config.TIMEZONE)


def parse_datetime(date_str: str, time_str: str) -> datetime:
    """Parse a date string and a time string typed by a staff member into an
    aware UTC datetime. Accepts a wide range of formats, e.g.
    date='2025-01-30' or '01/30/2025', time='9:00 AM' or '21:00'.
    """
    combined = f"{date_str.strip()} {time_str.strip()}"
    dt = dateparser.parse(combined)
    if dt is None:
        raise ValueError(f"Could not parse '{combined}'")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(timezone.utc)


def fmt(iso_str: str) -> str:
    """Format a stored ISO (UTC) timestamp for display in the configured
    local timezone."""
    dt = datetime.fromisoformat(iso_str).astimezone(TZ)
    return dt.strftime("%A, %B %d, %Y at %I:%M %p %Z")
