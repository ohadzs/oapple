# oapple — developer context

A unified Apple CLI for macOS. Which lists, calendars or contacts a given user keeps their data in
is configuration, not code — none of it belongs in this repo.

## What this is
One command, `oapple`, over **reminders, calendar, contacts, notes, system, shortcuts, clock**.
One I/O-free core per domain (`oapple/*.py`) plus a single CLI adapter (`oapple/cli.py`).
Reminders/calendar → EventKit; contacts → Contacts framework; notes/system → osascript;
shortcuts → `/usr/bin/shortcuts`; clock built in-repo.

**CLI-only by design.** The caller is always on the local Mac and always has a shell, so an MCP
adapter would buy nothing. A deliberate choice, not an omission.

## Dev facts
- Install: `uv venv && uv pip install -e .`; entry `oapple.cli:main`.
- Run: `oapple <domain> <command>`. Put `--json` *before* the domain for machine-readable output.
- First run prompts for Calendars / Reminders / Contacts access (Privacy & Security) for whichever
  app launched it.

## Gotchas
- **Re-`show` reminders before mutating them.** The list index goes stale otherwise, and a stale
  index hits the wrong item. This is the most common way to break something here.
- No Messages support (needs TCC / Full Disk Access) and no brightness or Focus control (no clean
  API). Don't add half-working versions of these.
