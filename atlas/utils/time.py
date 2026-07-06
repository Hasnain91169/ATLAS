from __future__ import annotations

from datetime import date, datetime, time, timezone, tzinfo

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - zoneinfo is stdlib in 3.11
    ZoneInfo = None


def resolve_timezone(name: str) -> tzinfo:
    if name.upper() == "UTC":
        return timezone.utc
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    local_tz = datetime.now().astimezone().tzinfo
    return local_tz or timezone.utc


def today_in_timezone(tz: tzinfo) -> date:
    return datetime.now(tz).date()


def combine_date_time(day: date, t: time, tz: tzinfo) -> datetime:
    return datetime.combine(day, t, tzinfo=tz)
