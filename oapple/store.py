"""Shared EventKit store for calendar + reminders.

EventKit's EKEventStore serves both events and reminders, but each entity type needs
its own access grant. We request lazily and cache the granted store so a session only
prompts once per entity type.
"""
import threading

from EventKit import EKEventStore, EKEntityTypeEvent, EKEntityTypeReminder
from Foundation import NSDate
from datetime import datetime

_store = None
_granted = set()  # entity types we've already been granted


def _ns_to_dt(nsdate) -> datetime:
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970())


def _dt_to_ns(dt: datetime) -> NSDate:
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _request(store, entity_type: int, timeout: float) -> None:
    done = threading.Event()
    result = {"granted": False, "err": None}

    def handler(granted, err):
        result["granted"] = bool(granted)
        result["err"] = err
        done.set()

    if entity_type == EKEntityTypeEvent and hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(handler)
    elif entity_type == EKEntityTypeReminder and hasattr(store, "requestFullAccessToRemindersWithCompletion_"):
        store.requestFullAccessToRemindersWithCompletion_(handler)
    else:  # macOS < 14
        store.requestAccessToEntityType_completion_(entity_type, handler)

    if not done.wait(timeout):
        raise TimeoutError("Timed out waiting for access prompt.")
    if not result["granted"]:
        kind = "Reminders" if entity_type == EKEntityTypeReminder else "Calendars"
        raise PermissionError(
            f"{kind} access not granted. Grant it in System Settings → Privacy & "
            f"Security → {kind} for the launching app (Terminal/python)."
        )


def get_store(entity_type: int = EKEntityTypeEvent, timeout: float = 30.0) -> EKEventStore:
    """Return the shared EKEventStore, requesting access for `entity_type` once."""
    global _store
    if _store is None:
        _store = EKEventStore.alloc().init()
    if entity_type not in _granted:
        _request(_store, entity_type, timeout)
        _granted.add(entity_type)
    return _store
