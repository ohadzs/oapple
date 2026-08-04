"""Natural-language date parsing for due dates and event times.

Supports the forms we actually type: 'today', 'tomorrow', 'yesterday', weekday names
('monday', 'mon' — next occurrence), '+Nd' / 'Nd' (N days out), ISO 'YYYY-MM-DD',
ISO with time 'YYYY-MM-DD HH:MM', and a bare 'HH:MM' (today at that time).

parse_when() returns (datetime, has_time): has_time=False means a date-only value
(midnight), so callers can decide whether to attach an alarm.
"""
from datetime import datetime, timedelta

from Foundation import NSDateComponents

_WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


def _next_weekday(target: int) -> datetime:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ahead = (target - today.weekday()) % 7
    if ahead == 0:
        ahead = 7  # "monday" on a Monday means next Monday, not today
    return today + timedelta(days=ahead)


def parse_when(s: str) -> tuple[datetime, bool]:
    """Parse a date/time string. Returns (datetime, has_time)."""
    raw = s.strip()
    low = raw.lower()
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if low in ("today", "tod"):
        return midnight, False
    if low in ("tomorrow", "tmr", "tom"):
        return midnight + timedelta(days=1), False
    if low == "yesterday":
        return midnight - timedelta(days=1), False
    if low in _WEEKDAYS:
        return _next_weekday(_WEEKDAYS[low]), False

    # +Nd / Nd  (N days from today)
    rel = low[1:] if low.startswith("+") else low
    if rel.endswith("d") and rel[:-1].isdigit():
        return midnight + timedelta(days=int(rel[:-1])), False

    # ISO datetime / date, tolerant of a space or 'T' separator
    for fmt, has_time in (
        ("%Y-%m-%d %H:%M", True), ("%Y-%m-%dT%H:%M", True),
        ("%Y-%m-%d %H:%M:%S", True), ("%Y-%m-%d", False),
        ("%d/%m/%Y %H:%M", True), ("%d/%m/%Y", False),
    ):
        try:
            return datetime.strptime(raw, fmt), has_time
        except ValueError:
            pass

    # bare HH:MM -> today at that time
    try:
        t = datetime.strptime(raw, "%H:%M")
        return midnight.replace(hour=t.hour, minute=t.minute), True
    except ValueError:
        pass

    raise ValueError(
        f"Could not parse date {s!r}. Try 'tomorrow', 'monday', '+3d', "
        f"'2026-06-29', or '2026-06-29 09:00'."
    )


def to_components(dt: datetime, has_time: bool) -> NSDateComponents:
    """Build an NSDateComponents for an EKReminder due date."""
    comps = NSDateComponents.alloc().init()
    comps.setYear_(dt.year)
    comps.setMonth_(dt.month)
    comps.setDay_(dt.day)
    if has_time:
        comps.setHour_(dt.hour)
        comps.setMinute_(dt.minute)
    return comps
