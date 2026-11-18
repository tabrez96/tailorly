"""Pure helpers for the customers list: query parsing, search and add-sheet prefill."""

from django.db.models import Q

from accounts.phones import is_valid_phone, normalize_phone

MAX_LENGTH = 80


def parse_query(params) -> str:
    return params.get("q", "").strip()[:MAX_LENGTH]


def search_filter(q: str) -> Q:
    """Match the name, or the phone when the text holds digits."""
    cond = Q(name__icontains=q)
    text = q.lstrip()
    if text.startswith("+91"):
        # An explicit country prefix is not part of the stored number.
        text = text[3:]
    digits = normalize_phone(text)
    if digits:
        cond |= Q(phone__contains=digits)
    return cond


def add_initial(text: str) -> dict:
    """Prefill for the add sheet: a phone number fills the phone, else the name."""
    text = text.strip()[:MAX_LENGTH]
    phone = normalize_phone(text)
    if is_valid_phone(phone):
        return {"phone": phone}
    return {"name": text} if text else {}
