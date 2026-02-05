"""Project-wide timezone configuration (default: America/Toronto)."""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "America/Toronto"))


def now() -> datetime:
    """Return current datetime in project timezone."""
    return datetime.now(TIMEZONE)
