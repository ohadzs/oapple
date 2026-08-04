"""I/O-free Contacts core (PyObjC Contacts framework).

Replaces ad-hoc AppleScript for read/search/add. Edit/delete of existing contacts
also go through CNSaveRequest. Access is requested once per session.
"""
import threading

from Contacts import (
    CNContactStore, CNEntityTypeContacts, CNMutableContact, CNSaveRequest,
    CNLabeledValue, CNPhoneNumber, CNContact,
    CNContactGivenNameKey, CNContactFamilyNameKey, CNContactOrganizationNameKey,
    CNContactPhoneNumbersKey, CNContactEmailAddressesKey, CNContactIdentifierKey,
    CNLabelHome, CNLabelWork,
)

_store = None

_KEYS = [
    CNContactGivenNameKey, CNContactFamilyNameKey, CNContactOrganizationNameKey,
    CNContactPhoneNumbersKey, CNContactEmailAddressesKey, CNContactIdentifierKey,
]


def _get_store(timeout: float = 30.0) -> CNContactStore:
    global _store
    if _store is not None:
        return _store
    store = CNContactStore.alloc().init()
    done = threading.Event()
    result = {"granted": False}

    def handler(granted, err):
        result["granted"] = bool(granted)
        done.set()

    store.requestAccessForEntityType_completionHandler_(CNEntityTypeContacts, handler)
    if not done.wait(timeout):
        raise TimeoutError("Timed out waiting for Contacts access prompt.")
    if not result["granted"]:
        raise PermissionError(
            "Contacts access not granted. Grant it in System Settings → Privacy & "
            "Security → Contacts for the launching app (Terminal/python)."
        )
    _store = store
    return store


def _contact_to_dict(c) -> dict:
    phones = [str(v.value().stringValue()) for v in (c.phoneNumbers() or [])]
    emails = [str(v.value()) for v in (c.emailAddresses() or [])]
    name = " ".join(p for p in (c.givenName(), c.familyName()) if p).strip()
    return {
        "id": c.identifier(),
        "name": name or c.organizationName(),
        "given": c.givenName(),
        "family": c.familyName(),
        "organization": c.organizationName(),
        "phones": phones,
        "emails": emails,
    }


def search(query: str) -> list[dict]:
    """Find contacts whose name matches `query`."""
    store = _get_store()
    pred = CNContact.predicateForContactsMatchingName_(query)
    matches, err = store.unifiedContactsMatchingPredicate_keysToFetch_error_(
        pred, _KEYS, None)
    if matches is None:
        raise RuntimeError(f"Contacts search failed: {err}")
    return [_contact_to_dict(c) for c in matches]


def get(identifier: str) -> dict:
    store = _get_store()
    c, err = store.unifiedContactWithIdentifier_keysToFetch_error_(identifier, _KEYS, None)
    if c is None:
        raise ValueError(f"No contact with id {identifier!r}: {err}")
    return _contact_to_dict(c)


def add(given: str, family: str = "", phone: str | None = None,
        email: str | None = None, organization: str | None = None) -> dict:
    store = _get_store()
    c = CNMutableContact.alloc().init()
    c.setGivenName_(given)
    if family:
        c.setFamilyName_(family)
    if organization:
        c.setOrganizationName_(organization)
    if phone:
        c.setPhoneNumbers_([CNLabeledValue.labeledValueWithLabel_value_(
            CNLabelHome, CNPhoneNumber.phoneNumberWithStringValue_(phone))])
    if email:
        c.setEmailAddresses_([CNLabeledValue.labeledValueWithLabel_value_(
            CNLabelHome, email)])
    req = CNSaveRequest.alloc().init()
    req.addContact_toContainerWithIdentifier_(c, None)
    ok, err = store.executeSaveRequest_error_(req, None)
    if not ok:
        raise RuntimeError(f"Failed to save contact: {err}")
    return _contact_to_dict(c)


def delete(identifier: str) -> str:
    store = _get_store()
    c, err = store.unifiedContactWithIdentifier_keysToFetch_error_(identifier, _KEYS, None)
    if c is None:
        raise ValueError(f"No contact with id {identifier!r}: {err}")
    name = " ".join(p for p in (c.givenName(), c.familyName()) if p).strip()
    req = CNSaveRequest.alloc().init()
    req.deleteContact_(c.mutableCopy())
    ok, err = store.executeSaveRequest_error_(req, None)
    if not ok:
        raise RuntimeError(f"Failed to delete contact: {err}")
    return name
