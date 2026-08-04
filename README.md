# oapple — a unified Apple CLI for macOS

One CLI over the Mac: **reminders, calendar, contacts, notes, system, shortcuts, clock**.
Replaces the separate `reminders-cli` (Swift) and `calendar-cli` (Python) and a pile of
ad-hoc AppleScript.

## Design

Per the hub's tooling standard: **one I/O-free core per domain** (`oapple/*.py`) plus a
single **CLI adapter** (`oapple/cli.py`). The cores print nothing and parse no args, so an
MCP adapter could be added later in ~30 lines — but it isn't built, on purpose: these run
**locally on a Mac**, the only caller is Claude (which always has a shell), and nothing
here can be distributed, so MCP's "always-on, model-facing reach" buys nothing while a
long-running MCP would serve stale code. CLI it is.

- **reminders + calendar** → EventKit (`pyobjc-framework-EventKit`), shared `EKEventStore`.
- **contacts** → Contacts framework (`pyobjc-framework-Contacts`).
- **notes** → AppleScript (`osascript`); Apple ships no Notes framework.
- **system** → osascript / pmset / networksetup / pbcopy.
- **shortcuts** → the `/usr/bin/shortcuts` CLI (escape hatch to app actions with no script dictionary).
- **clock** → built ourselves (the Clock app isn't scriptable): `zoneinfo` world clock + detached timers.

Not included, and why: **messages** (Messages' `chat.db` is TCC-protected — needs Full
Disk Access), **brightness / Focus-DND** (no clean public API — do Focus via a Shortcut).

## Install

```sh
uv venv && uv pip install -e .
```

First run prompts for Calendars / Reminders / Contacts access (System Settings →
Privacy & Security) for the launching app (Terminal/python).

## Usage

Add `--json` (before the domain) for machine-readable output.

```sh
# reminders
oapple reminders today                      # due today + overdue, across all lists
oapple reminders show Personal              # 1-indexed list
oapple reminders add Personal "buy milk" -d tomorrow
oapple reminders add Personal "grab the book" --at "1 Infinite Loop, Cupertino"  # geofence: fires on arrival
oapple reminders add Personal "lock up" --at "32.07,34.81" --radius 50 --on-leave  # fires on departure
oapple reminders edit Personal 2 -d monday  # move due date (the gap that started this)
oapple reminders done Personal 2
oapple reminders delete Personal 2
oapple reminders lists

# calendar
oapple calendar today
oapple calendar week
oapple calendar create "2026-06-30 09:00" Standup --cal Personal
oapple calendar events 2026-07-01 2026-07-08
oapple calendar calendars

# contacts
oapple contacts search dafna
oapple contacts add Jane --family Doe --phone 054-1234567
oapple contacts delete <id>

# notes
oapple notes list
oapple notes read "Shopping"
oapple notes create "Ideas" --body "first line"
oapple notes append "Ideas" "another line"
```

## Dates

`--due` / event times accept: `today`, `tomorrow`, `monday` (next one), `+3d`,
`2026-06-29`, `2026-06-29 09:00`, or `09:00` (today). A time attaches an alarm;
date-only does not.
