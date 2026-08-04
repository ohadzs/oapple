"""I/O-free EventKit reminders core (EKReminder).

Replaces the Swift reminders-cli. Lists map to EKCalendar(EKEntityTypeReminder);
fetching reminders is async in EventKit, so we block on a completion handler.
Reminders are addressed by 1-based index within a list (stable for a given fetch),
mirroring the old CLI's `show`/`edit`/`complete` index argument.
"""
import threading

from EventKit import (EKEntityTypeReminder, EKReminder, EKAlarm,
                      EKStructuredLocation, EKAlarmProximityEnter,
                      EKAlarmProximityLeave)

from .store import get_store, _dt_to_ns, _ns_to_dt
from .dates import parse_when, to_components


def _geocode(address: str):
    """Address string -> (lat, lng). Blocks on CLGeocoder, pumping the runloop.

    CLGeocoder delivers its completion on the main runloop, so a plain
    threading.Event wait returns an EMPTY result — the runloop must be pumped.
    """
    from CoreLocation import CLGeocoder
    from Foundation import NSRunLoop, NSDate
    g = CLGeocoder.alloc().init()
    box = {}

    def handler(placemarks, err):
        box["p"] = list(placemarks) if placemarks else []

    g.geocodeAddressString_completionHandler_(address, handler)
    rl = NSRunLoop.currentRunLoop()
    for _ in range(60):  # up to ~15s
        rl.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.25))
        if "p" in box:
            break
    placemarks = box.get("p", [])
    if not placemarks:
        raise ValueError(f"Could not geocode location {address!r}.")
    c = placemarks[0].location().coordinate()
    return c.latitude, c.longitude


def _location_alarm(at: str, radius: float = 100.0, on_leave: bool = False):
    """Build a geofence EKAlarm from `at` ('lat,lng' or an address) + radius (m)."""
    from CoreLocation import CLLocation
    title = at
    try:
        lat_s, lng_s = at.split(",", 1)
        lat, lng = float(lat_s), float(lng_s)
    except (ValueError, AttributeError):
        lat, lng = _geocode(at)
    loc = EKStructuredLocation.locationWithTitle_(title)
    loc.setGeoLocation_(CLLocation.alloc().initWithLatitude_longitude_(lat, lng))
    loc.setRadius_(radius)
    alarm = EKAlarm.alloc().init()
    alarm.setStructuredLocation_(loc)
    alarm.setProximity_(EKAlarmProximityLeave if on_leave else EKAlarmProximityEnter)
    return alarm


def _store():
    return get_store(EKEntityTypeReminder)


def list_lists() -> list[dict]:
    store = _store()
    return [
        {"title": c.title(), "id": c.calendarIdentifier(),
         "allows_modify": bool(c.allowsContentModifications())}
        for c in store.calendarsForEntityType_(EKEntityTypeReminder)
    ]


def _find_list(store, name: str):
    wanted = name.lower()
    for c in store.calendarsForEntityType_(EKEntityTypeReminder):
        if c.title().lower() == wanted:
            return c
    return None


def _reminder_to_dict(r, index: int | None = None) -> dict:
    due = r.dueDateComponents()
    due_date = None
    if due is not None and due.date() is not None:
        due_date = _ns_to_dt(due.date())
    return {
        "index": index,
        "title": r.title(),
        "id": r.calendarItemIdentifier(),
        "list": r.calendar().title(),
        "completed": bool(r.isCompleted()),
        "due": due_date,
        "has_time": due is not None and due.hour() != 9223372036854775807,  # NSNotFound => date-only
        "priority": int(r.priority()),
        "notes": r.notes(),
    }


def _fetch(store, predicate, timeout: float = 30.0) -> list:
    done = threading.Event()
    box = {"items": []}

    def handler(reminders):
        box["items"] = list(reminders or [])
        done.set()

    store.fetchRemindersMatchingPredicate_completion_(predicate, handler)
    if not done.wait(timeout):
        raise TimeoutError("Timed out fetching reminders.")
    return box["items"]


def _creation_key(r):
    """Deterministic sort key so a 1-based index is STABLE across separate fetches.

    EventKit returns reminders in arbitrary order per call, so without this an index
    from `show` could resolve to a different reminder in `edit`/`delete` — corrupting
    or deleting the wrong item. creationDate is stable; identifier breaks ties.
    """
    cd = r.creationDate()
    return (cd.timeIntervalSince1970() if cd is not None else 0.0,
            r.calendarItemIdentifier())


def _visible(store, list_name: str, include_completed: bool, only_completed: bool):
    """The filtered, deterministically-ordered reminders in a list.

    `show` and `_resolve` MUST call this with the same filter so their indexes agree.
    """
    cal = _find_list(store, list_name)
    if cal is None:
        raise ValueError(f"List {list_name!r} not found.")
    items = sorted(_fetch(store, store.predicateForRemindersInCalendars_([cal])),
                   key=_creation_key)
    out = []
    for r in items:
        if r.isCompleted() and not (include_completed or only_completed):
            continue
        if not r.isCompleted() and only_completed:
            continue
        out.append(r)
    return out


def show(list_name: str, include_completed: bool = False,
         only_completed: bool = False) -> list[dict]:
    """Reminders in a list, 1-indexed (stable). Incomplete only unless flags say otherwise."""
    store = _store()
    items = _visible(store, list_name, include_completed, only_completed)
    return [_reminder_to_dict(r, i) for i, r in enumerate(items, 1)]


def _resolve(store, list_name: str, index, include_completed: bool = False,
             only_completed: bool = False):
    """Resolve a 1-based index (or id) to an EKReminder, matching `show`'s ordering.

    The index MUST be read against the same view the caller saw it in:
    - default (no flags) → incomplete, like plain `show`
    - only_completed → the `show --completed` view (needed to un-complete or delete a done item)
    - include_completed → the `show --all` view
    An explicit id resolves regardless of view.
    """
    # An explicit calendarItemIdentifier is unambiguous; try it first.
    items = _visible(store, list_name, include_completed=True, only_completed=False)
    for r in items:
        if r.calendarItemIdentifier() == str(index):
            return r
    visible = _visible(store, list_name, include_completed, only_completed)
    try:
        i = int(index)
    except (TypeError, ValueError):
        raise ValueError(f"No reminder matching {index!r} in {list_name!r}.")
    if i < 1 or i > len(visible):
        view = "completed" if only_completed else ("all" if include_completed else "open")
        raise ValueError(f"No reminder at index {i} in {list_name!r} ({view} view, "
                         f"{len(visible)} items). Re-run `show` to get a fresh index.")
    return visible[i - 1]


def add(list_name: str, title: str, due: str | None = None,
        notes: str | None = None, at: str | None = None,
        radius: float = 100.0, on_leave: bool = False) -> dict:
    store = _store()
    cal = _find_list(store, list_name)
    if cal is None:
        raise ValueError(f"List {list_name!r} not found.")
    r = EKReminder.reminderWithEventStore_(store)
    r.setCalendar_(cal)
    r.setTitle_(title)
    if notes is not None:
        r.setNotes_(notes)
    if due is not None:
        _apply_due(r, due)
    if at is not None:
        r.addAlarm_(_location_alarm(at, radius, on_leave))
    ok, err = store.saveReminder_commit_error_(r, True, None)
    if not ok:
        raise RuntimeError(f"Failed to save reminder: {err}")
    return _reminder_to_dict(r)


def _apply_due(r, due: str) -> None:
    dt, has_time = parse_when(due)
    r.setDueDateComponents_(to_components(dt, has_time))
    for alarm in list(r.alarms() or []):
        r.removeAlarm_(alarm)
    if has_time:
        r.addAlarm_(EKAlarm.alarmWithAbsoluteDate_(_dt_to_ns(dt)))


def edit(list_name: str, index, title: str | None = None,
         due: str | None = None, notes: str | None = None,
         include_completed: bool = False, only_completed: bool = False) -> dict:
    store = _store()
    r = _resolve(store, list_name, index, include_completed, only_completed)
    if title is not None:
        r.setTitle_(title)
    if notes is not None:
        r.setNotes_(notes)
    if due is not None:
        _apply_due(r, due)
    ok, err = store.saveReminder_commit_error_(r, True, None)
    if not ok:
        raise RuntimeError(f"Failed to update reminder: {err}")
    return _reminder_to_dict(r)


def set_complete(list_name: str, index, complete: bool = True) -> dict:
    store = _store()
    # Un-completing a reminder means the target is in the completed view, not the open one.
    r = _resolve(store, list_name, index, only_completed=not complete)
    r.setCompleted_(complete)
    ok, err = store.saveReminder_commit_error_(r, True, None)
    if not ok:
        raise RuntimeError(f"Failed to update reminder: {err}")
    return _reminder_to_dict(r)


def delete(list_name: str, index, include_completed: bool = False,
           only_completed: bool = False) -> str:
    store = _store()
    r = _resolve(store, list_name, index, include_completed, only_completed)
    title = r.title()
    ok, err = store.removeReminder_commit_error_(r, True, None)
    if not ok:
        raise RuntimeError(f"Failed to delete reminder: {err}")
    return title


def today(include_overdue: bool = True) -> list[dict]:
    """Incomplete reminders due today (and earlier, if include_overdue)."""
    from datetime import datetime, timedelta
    store = _store()
    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    start = None if include_overdue else end.replace(hour=0, minute=0, second=0)
    pred = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
        _dt_to_ns(start) if start else None, _dt_to_ns(end), None)
    items = _fetch(store, pred)
    out = [_reminder_to_dict(r) for r in items if r.dueDateComponents() is not None]
    out.sort(key=lambda x: (x["due"] or x["due"]))
    return out
