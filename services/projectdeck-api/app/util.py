import re
from datetime import date, datetime, timezone


def slugify(value: str) -> str:
    s = value.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "projekt"


def today() -> date:
    return datetime.now(timezone.utc).date()


def week_iso(d: date | None = None) -> str:
    d = d or today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"
