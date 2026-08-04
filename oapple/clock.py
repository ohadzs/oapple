"""I/O-free clock core — built ourselves (the macOS Clock app isn't scriptable).

World clock + 'now' are pure stdlib zoneinfo. Timers run as a detached background
process that fires a macOS notification + sound when done — fine for short timers
while the Mac is awake; for anything that must survive sleep, use a reminder/calendar
event (which sync to the phone) instead.
"""
import subprocess
import sys
import re
from datetime import datetime
from zoneinfo import ZoneInfo

# Friendly city names → IANA tz. Unknown names fall through to ZoneInfo(name) so
# 'Asia/Tokyo' style ids work too.
CITIES = {
    "israel": "Asia/Jerusalem", "tel aviv": "Asia/Jerusalem", "jerusalem": "Asia/Jerusalem",
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "new york": "America/New_York", "nyc": "America/New_York",
    "sf": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "london": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "bangkok": "Asia/Bangkok", "sydney": "Australia/Sydney", "utc": "UTC",
}
DEFAULT_CITIES = ["israel", "tokyo", "london", "new york", "sf"]


def now() -> dict:
    n = datetime.now().astimezone()
    return {"time": n.strftime("%H:%M:%S"), "date": n.strftime("%Y-%m-%d"),
            "tz": str(n.tzinfo)}


def _zone(name: str) -> ZoneInfo:
    key = CITIES.get(name.lower().strip(), name)
    try:
        return ZoneInfo(key)
    except Exception:
        raise ValueError(f"Unknown city/timezone {name!r}. "
                         f"Try one of: {', '.join(sorted(CITIES))}, or an id like 'Asia/Tokyo'.")


def world(cities: list[str] | None = None) -> list[dict]:
    cities = cities or DEFAULT_CITIES
    out = []
    for c in cities:
        z = _zone(c)
        t = datetime.now(z)
        out.append({"city": c, "tz": str(z), "time": t.strftime("%H:%M"),
                    "date": t.strftime("%Y-%m-%d"), "day": t.strftime("%a")})
    return out


_DUR = re.compile(r"(\d+)\s*([hms])", re.I)


def parse_duration(s: str) -> int:
    """'10m' '1h30m' '90s' -> seconds. A bare number is minutes."""
    s = s.strip()
    if s.isdigit():
        return int(s) * 60
    total, found = 0, False
    for num, unit in _DUR.findall(s):
        found = True
        total += int(num) * {"h": 3600, "m": 60, "s": 1}[unit.lower()]
    if not found:
        raise ValueError(f"Could not parse duration {s!r}. Try '10m', '1h30m', '90s'.")
    return total


def timer(duration: str, label: str = "Timer") -> dict:
    """Start a detached countdown that notifies on completion. Non-blocking."""
    seconds = parse_duration(duration)
    title = "oapple timer"
    notif = (f'display notification {label!r} with title {title!r} '
             f'sound name "Glass"')
    # Detached child: sleep, then notify. Survives the CLI exiting.
    child = (f"import time,subprocess;time.sleep({seconds});"
             f"subprocess.run(['osascript','-e',{notif!r}])")
    subprocess.Popen([sys.executable, "-c", child], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"label": label, "seconds": seconds, "duration": duration}
