"""I/O-free EventKit calendar core.

EventKit's event-query predicate expands recurring events (birthdays, weekly repeats)
into concrete occurrences — which AppleScript could not do.
"""
from datetime import datetime, timedelta

from EventKit import EKEntityTypeEvent, EKEvent, EKSpanThisEvent

from .store import get_store, _ns_to_dt, _dt_to_ns


def _store():
    return get_store(EKEntityTypeEvent)


def list_calendars() -> list[dict]:
    store = _store()
    return [
        {"title": c.title(), "id": c.calendarIdentifier(),
         "allows_modify": bool(c.allowsContentModifications())}
        for c in store.calendarsForEntityType_(EKEntityTypeEvent)
    ]


def _find_calendar(store, name: str):
    wanted = name.lower()
    for c in store.calendarsForEntityType_(EKEntityTypeEvent):
        if c.title().lower() == wanted:
            return c
    return None


def _event_to_dict(e) -> dict:
    return {
        "title": e.title(),
        "id": e.eventIdentifier(),
        "start": _ns_to_dt(e.startDate()),
        "end": _ns_to_dt(e.endDate()) if e.endDate() else None,
        "all_day": bool(e.isAllDay()),
        "calendar": e.calendar().title(),
        "location": e.location(),
        "notes": e.notes(),
        "recurring": e.hasRecurrenceRules(),
    }


def list_events(start: datetime, end: datetime, calendars: list[str] | None = None) -> list[dict]:
    """Events between start and end, with recurrences expanded to occurrences."""
    store = _store()
    cals = None
    if calendars:
        wanted = {x.lower() for x in calendars}
        cals = [c for c in store.calendarsForEntityType_(EKEntityTypeEvent)
                if c.title().lower() in wanted]
    pred = store.predicateForEventsWithStartDate_endDate_calendars_(
        _dt_to_ns(start), _dt_to_ns(end), cals)
    events = store.eventsMatchingPredicate_(pred) or []
    out = [_event_to_dict(e) for e in events]
    out.sort(key=lambda x: x["start"])
    return out


def create_event(title: str, start: datetime, end: datetime | None = None,
                 calendar: str = "Personal", all_day: bool = False,
                 notes: str | None = None, location: str | None = None) -> dict:
    """Create an event and return its dict. Default end: +1h (timed) / +1 day (all-day)."""
    store = _store()
    cal = _find_calendar(store, calendar)
    if cal is None:
        raise ValueError(f"Calendar {calendar!r} not found.")
    if not cal.allowsContentModifications():
        raise ValueError(f"Calendar {calendar!r} does not allow modifications.")
    if end is None:
        end = start + (timedelta(days=1) if all_day else timedelta(hours=1))

    event = EKEvent.eventWithEventStore_(store)
    event.setTitle_(title)
    event.setCalendar_(cal)
    event.setStartDate_(_dt_to_ns(start))
    event.setEndDate_(_dt_to_ns(end))
    event.setAllDay_(all_day)
    if notes is not None:
        event.setNotes_(notes)
    if location is not None:
        event.setLocation_(location)

    ok, err = store.saveEvent_span_error_(event, EKSpanThisEvent, None)
    if not ok:
        raise RuntimeError(f"Failed to save event: {err}")
    return _event_to_dict(event)


def delete_event(event_id: str) -> bool:
    """Delete an event by its identifier. Returns True on success."""
    store = _store()
    event = store.eventWithIdentifier_(event_id)
    if event is None:
        raise ValueError(f"No event with id {event_id!r}.")
    ok, err = store.removeEvent_span_error_(event, EKSpanThisEvent, None)
    if not ok:
        raise RuntimeError(f"Failed to delete event: {err}")
    return True
