"""oapple — unified Apple CLI: reminders, calendar, contacts, notes.

One I/O-free core per domain (core stays MCP-ready); this is the only adapter built.
Usage: oapple <domain> <command> ...   e.g.  oapple reminders today
Add --json (before the domain) for machine-readable output.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta

from . import reminders as rem
from . import calendar as cal
from . import contacts as con
from . import notes as nts
from . import system as sysm
from . import shortcuts as sc
from . import clock as clk
from .dates import parse_when


# ---------- output ----------

def _default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


def emit(data, plain_fn, as_json: bool):
    if as_json:
        print(json.dumps(data, default=_default, ensure_ascii=False, indent=2))
    else:
        plain_fn(data)


def _fmt_due(r) -> str:
    if not r.get("due"):
        return ""
    d = r["due"]
    return d.strftime("  (%Y-%m-%d %H:%M)" if r.get("has_time") else "  (%Y-%m-%d)")


# ---------- reminders ----------

def rem_today(a):
    emit(rem.today(include_overdue=not a.no_overdue),
         lambda rs: [print(f"{r['list']}: {r['title']}{_fmt_due(r)}") for r in rs] or
                    (print("(nothing due)") if not rs else None), a.json)

def rem_show(a):
    emit(rem.show(a.list, include_completed=a.all, only_completed=a.completed),
         lambda rs: [print(f"{r['index']}: {r['title']}{_fmt_due(r)}"
                           f"{'  ✓' if r['completed'] else ''}") for r in rs] or
                    (print("(empty)") if not rs else None), a.json)

def rem_lists(a):
    emit(rem.list_lists(), lambda ls: [print(l["title"]) for l in ls], a.json)

def rem_add(a):
    r = rem.add(a.list, " ".join(a.text), due=a.due, notes=a.notes,
                at=a.at, radius=a.radius, on_leave=a.on_leave)
    emit(r, lambda r: print(f"Added '{r['title']}' to {r['list']}{_fmt_due(r)}"), a.json)

def rem_edit(a):
    r = rem.edit(a.list, a.index, title=" ".join(a.text) or None, due=a.due, notes=a.notes,
                 include_completed=a.all, only_completed=a.completed)
    emit(r, lambda r: print(f"Updated '{r['title']}'{_fmt_due(r)}"), a.json)

def rem_done(a):
    r = rem.set_complete(a.list, a.index, complete=not a.undo)
    emit(r, lambda r: print(f"{'Uncompleted' if a.undo else 'Completed'} '{r['title']}'"), a.json)

def rem_delete(a):
    t = rem.delete(a.list, a.index, include_completed=a.all, only_completed=a.completed)
    emit({"deleted": t}, lambda d: print(f"Deleted '{d['deleted']}'"), a.json)


# ---------- calendar ----------

def _fmt_event(e) -> str:
    when = e["start"].strftime("%Y-%m-%d" if e["all_day"] else "%Y-%m-%d %H:%M")
    loc = f" @ {e['location']}" if e.get("location") else ""
    return f"{when}  {e['title']}  [{e['calendar']}]{loc}"

def cal_today(a):
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    emit(cal.list_events(start, start + timedelta(days=1), a.cal),
         lambda es: [print(_fmt_event(e)) for e in es] or
                    (print("(no events)") if not es else None), a.json)

def cal_week(a):
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    emit(cal.list_events(start, start + timedelta(days=7), a.cal),
         lambda es: [print(_fmt_event(e)) for e in es] or
                    (print("(no events)") if not es else None), a.json)

def cal_events(a):
    start, _ = parse_when(a.start)
    end, _ = parse_when(a.end)
    emit(cal.list_events(start, end, a.cal),
         lambda es: [print(_fmt_event(e)) for e in es], a.json)

def cal_calendars(a):
    emit(cal.list_calendars(),
         lambda cs: [print(f"{c['title']}{'' if c['allows_modify'] else '  (read-only)'}")
                     for c in cs], a.json)

def cal_create(a):
    start, _ = parse_when(a.start)
    end = parse_when(a.end)[0] if a.end else None
    e = cal.create_event(" ".join(a.title), start, end, calendar=a.cal or "Personal",
                         all_day=a.all_day, notes=a.notes, location=a.location)
    emit(e, lambda e: print(f"Created '{e['title']}' {_fmt_event(e)}"), a.json)

def cal_delete(a):
    cal.delete_event(a.id)
    emit({"deleted": a.id}, lambda d: print("Deleted event"), a.json)


# ---------- contacts ----------

def _fmt_contact(c) -> str:
    bits = [c["name"]]
    if c["phones"]:
        bits.append(", ".join(c["phones"]))
    if c["emails"]:
        bits.append(", ".join(c["emails"]))
    return "  |  ".join(bits)

def con_search(a):
    emit(con.search(" ".join(a.query)),
         lambda cs: [print(_fmt_contact(c)) for c in cs] or
                    (print("(no matches)") if not cs else None), a.json)

def con_add(a):
    c = con.add(a.given, family=a.family or "", phone=a.phone, email=a.email,
                organization=a.org)
    emit(c, lambda c: print(f"Added '{c['name']}'"), a.json)

def con_delete(a):
    name = con.delete(a.id)
    emit({"deleted": name}, lambda d: print(f"Deleted '{d['deleted']}'"), a.json)


# ---------- notes ----------

def nts_list(a):
    emit(nts.list_notes(a.folder),
         lambda ns: [print(f"{n['name']}  [{n['folder']}]") for n in ns], a.json)

def nts_folders(a):
    emit(nts.list_folders(), lambda fs: [print(f) for f in fs], a.json)

def nts_read(a):
    emit(nts.read(a.name), lambda n: print(f"# {n['name']}  [{n['folder']}]\n\n{n['body']}"),
         a.json)

def nts_create(a):
    n = nts.create(a.name, body=a.body or "", folder=a.folder)
    emit(n, lambda n: print(f"Created '{n['name']}' [{n['folder']}]"), a.json)

def nts_append(a):
    n = nts.append(a.name, a.text)
    emit(n, lambda n: print(f"Appended to '{n['name']}'"), a.json)

def nts_delete(a):
    name = nts.delete(a.name)
    emit({"deleted": name}, lambda d: print(f"Deleted '{d['deleted']}'"), a.json)


# ---------- system ----------

def _onoff(v: str | None) -> bool | None:
    if v is None or v == "toggle":
        return None
    return v in ("on", "true", "1", "yes")

def sys_volume(a):
    val = sysm.set_volume(a.level) if a.level is not None else sysm.get_volume()
    emit({"volume": val}, lambda d: print(f"volume {d['volume']}"), a.json)

def sys_dark(a):
    on = sysm.set_dark(_onoff(a.state)) if a.state else sysm.get_dark()
    emit({"dark": on}, lambda d: print(f"dark mode {'on' if d['dark'] else 'off'}"), a.json)

def sys_battery(a):
    emit(sysm.battery(), lambda d: print(f"{d['percent']}% ({d['state']}, {d['power']})"), a.json)

def sys_wifi(a):
    on = sysm.set_wifi(_onoff(a.state)) if a.state else sysm.get_wifi()
    emit({"wifi": on}, lambda d: print(f"wifi {'on' if d['wifi'] else 'off'}"), a.json)

def sys_clipboard(a):
    if a.text:
        sysm.set_clipboard(" ".join(a.text))
        emit({"set": True}, lambda d: print("clipboard set"), a.json)
    else:
        emit({"clipboard": sysm.get_clipboard()}, lambda d: print(d["clipboard"]), a.json)

def sys_sleep(a):
    sysm.sleep_now(); emit({"slept": True}, lambda d: print("sleeping"), a.json)

def sys_lock(a):
    sysm.lock_screen(); emit({"locked": True}, lambda d: print("locked"), a.json)


# ---------- shortcuts ----------

def sc_list(a):
    emit(sc.list_shortcuts(), lambda ns: [print(n) for n in ns], a.json)

def sc_run(a):
    out = sc.run(a.name, input_text=a.input)
    emit({"output": out}, lambda d: print(d["output"]) if d["output"] else
         print(f"ran '{a.name}'"), a.json)


# ---------- clock ----------

def clk_now(a):
    emit(clk.now(), lambda d: print(f"{d['time']}  {d['date']}  ({d['tz']})"), a.json)

def clk_world(a):
    emit(clk.world(a.cities or None),
         lambda ws: [print(f"{w['time']}  {w['day']} {w['date']}  {w['city']}") for w in ws],
         a.json)

def clk_timer(a):
    t = clk.timer(a.duration, " ".join(a.label) if a.label else "Timer")
    emit(t, lambda d: print(f"timer '{d['label']}' set for {d['duration']} "
                            f"({d['seconds']}s) — notifies when done"), a.json)


# ---------- parser ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="oapple",
                                description="Apple CLI: reminders, calendar, contacts, notes")
    p.add_argument("--json", action="store_true", help="machine-readable JSON output")
    dom = p.add_subparsers(dest="domain", required=True)

    # reminders
    r = dom.add_parser("reminders", aliases=["rem"], help="Apple Reminders").add_subparsers(
        dest="cmd", required=True)
    s = r.add_parser("today", help="reminders due today + overdue"); s.add_argument("--no-overdue", action="store_true"); s.set_defaults(fn=rem_today)
    s = r.add_parser("show", help="reminders in a list"); s.add_argument("list"); s.add_argument("--all", action="store_true", help="include completed"); s.add_argument("--completed", action="store_true"); s.set_defaults(fn=rem_show)
    s = r.add_parser("lists", help="reminder lists"); s.set_defaults(fn=rem_lists)
    s = r.add_parser("add", help="add a reminder"); s.add_argument("list"); s.add_argument("text", nargs="+"); s.add_argument("-d", "--due"); s.add_argument("-n", "--notes"); s.add_argument("--at", help="location geofence: 'lat,lng' or an address (fires on arrival)"); s.add_argument("--radius", type=float, default=100.0, help="geofence radius in meters (default 100)"); s.add_argument("--on-leave", action="store_true", help="fire when leaving the location instead of arriving"); s.set_defaults(fn=rem_add)
    s = r.add_parser("edit", help="edit a reminder by index"); s.add_argument("list"); s.add_argument("index"); s.add_argument("text", nargs="*"); s.add_argument("-d", "--due"); s.add_argument("-n", "--notes"); s.add_argument("--all", action="store_true", help="index is from `show --all`"); s.add_argument("--completed", action="store_true", help="index is from `show --completed`"); s.set_defaults(fn=rem_edit)
    s = r.add_parser("done", help="complete (or --undo) a reminder"); s.add_argument("list"); s.add_argument("index"); s.add_argument("--undo", action="store_true", help="un-complete (index from `show --completed`)"); s.set_defaults(fn=rem_done)
    s = r.add_parser("delete", help="delete a reminder"); s.add_argument("list"); s.add_argument("index"); s.add_argument("--all", action="store_true", help="index is from `show --all`"); s.add_argument("--completed", action="store_true", help="index is from `show --completed`"); s.set_defaults(fn=rem_delete)

    # calendar
    c = dom.add_parser("calendar", aliases=["cal"], help="Apple Calendar").add_subparsers(
        dest="cmd", required=True)
    s = c.add_parser("today", help="today's events"); s.add_argument("--cal", nargs="*"); s.set_defaults(fn=cal_today)
    s = c.add_parser("week", help="next 7 days"); s.add_argument("--cal", nargs="*"); s.set_defaults(fn=cal_week)
    s = c.add_parser("events", help="events in a date range"); s.add_argument("start"); s.add_argument("end"); s.add_argument("--cal", nargs="*"); s.set_defaults(fn=cal_events)
    s = c.add_parser("calendars", help="list calendars"); s.set_defaults(fn=cal_calendars)
    s = c.add_parser("create", help="create an event"); s.add_argument("start"); s.add_argument("title", nargs="+"); s.add_argument("--end"); s.add_argument("--cal"); s.add_argument("--all-day", action="store_true"); s.add_argument("--notes"); s.add_argument("--location"); s.set_defaults(fn=cal_create)
    s = c.add_parser("delete", help="delete an event by id"); s.add_argument("id"); s.set_defaults(fn=cal_delete)

    # contacts
    o = dom.add_parser("contacts", aliases=["con"], help="Apple Contacts").add_subparsers(
        dest="cmd", required=True)
    s = o.add_parser("search", help="search by name"); s.add_argument("query", nargs="+"); s.set_defaults(fn=con_search)
    s = o.add_parser("add", help="add a contact"); s.add_argument("given"); s.add_argument("--family"); s.add_argument("--phone"); s.add_argument("--email"); s.add_argument("--org"); s.set_defaults(fn=con_add)
    s = o.add_parser("delete", help="delete a contact by id"); s.add_argument("id"); s.set_defaults(fn=con_delete)

    # notes
    n = dom.add_parser("notes", help="Apple Notes").add_subparsers(dest="cmd", required=True)
    s = n.add_parser("list", help="list notes"); s.add_argument("--folder"); s.set_defaults(fn=nts_list)
    s = n.add_parser("folders", help="list folders"); s.set_defaults(fn=nts_folders)
    s = n.add_parser("read", help="read a note"); s.add_argument("name"); s.set_defaults(fn=nts_read)
    s = n.add_parser("create", help="create a note"); s.add_argument("name"); s.add_argument("--body"); s.add_argument("--folder"); s.set_defaults(fn=nts_create)
    s = n.add_parser("append", help="append text to a note"); s.add_argument("name"); s.add_argument("text"); s.set_defaults(fn=nts_append)
    s = n.add_parser("delete", help="delete a note"); s.add_argument("name"); s.set_defaults(fn=nts_delete)

    # system
    y = dom.add_parser("system", aliases=["sys"], help="Mac controls").add_subparsers(
        dest="cmd", required=True)
    s = y.add_parser("volume", help="get/set output volume 0-100"); s.add_argument("level", nargs="?", type=int); s.set_defaults(fn=sys_volume)
    s = y.add_parser("dark", help="dark mode on|off|toggle"); s.add_argument("state", nargs="?", choices=["on", "off", "toggle"]); s.set_defaults(fn=sys_dark)
    s = y.add_parser("battery", help="battery status"); s.set_defaults(fn=sys_battery)
    s = y.add_parser("wifi", help="wifi on|off"); s.add_argument("state", nargs="?", choices=["on", "off"]); s.set_defaults(fn=sys_wifi)
    s = y.add_parser("clipboard", aliases=["clip"], help="get clipboard, or set from text"); s.add_argument("text", nargs="*"); s.set_defaults(fn=sys_clipboard)
    s = y.add_parser("sleep", help="sleep the Mac"); s.set_defaults(fn=sys_sleep)
    s = y.add_parser("lock", help="lock the screen"); s.set_defaults(fn=sys_lock)

    # shortcuts
    h = dom.add_parser("shortcuts", aliases=["sc"], help="run Apple Shortcuts").add_subparsers(
        dest="cmd", required=True)
    s = h.add_parser("list", help="list shortcuts"); s.set_defaults(fn=sc_list)
    s = h.add_parser("run", help="run a shortcut by name"); s.add_argument("name"); s.add_argument("-i", "--input"); s.set_defaults(fn=sc_run)

    # clock
    k = dom.add_parser("clock", help="world clock + timers").add_subparsers(
        dest="cmd", required=True)
    s = k.add_parser("now", help="local time"); s.set_defaults(fn=clk_now)
    s = k.add_parser("world", help="time in cities (default: a useful set)"); s.add_argument("cities", nargs="*"); s.set_defaults(fn=clk_world)
    s = k.add_parser("timer", help="countdown -> notification"); s.add_argument("duration"); s.add_argument("label", nargs="*"); s.set_defaults(fn=clk_timer)

    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.fn(args)
    except (ValueError, PermissionError, TimeoutError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
