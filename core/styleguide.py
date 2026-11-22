"""Demo forms and sample data for the styleguide page only."""

from django import forms
from django.templatetags.static import static


class ControlsForm(forms.Form):
    due = forms.CharField(label="Due date")
    assign = forms.ChoiceField(
        label="Assign to", choices=[("ali", "Ali Khan"), ("sana", "Sana Begum")]
    )
    advance = forms.CharField(
        label="Advance received (₹)", help_text="Leave empty if nothing was paid yet."
    )
    who_pays = forms.ChoiceField(
        label="Who pays",
        widget=forms.RadioSelect,
        choices=[("customer", "Customer"), ("free", "Free: self or family")],
    )
    method = forms.ChoiceField(
        label="Method",
        widget=forms.RadioSelect,
        choices=[("cash", "Cash"), ("upi", "UPI"), ("card", "Card"), ("bank", "Bank")],
    )
    mcp = forms.BooleanField(
        label="MCP server", required=False, help_text="On · 2 apps connected"
    )
    staff_pay = forms.BooleanField(
        label="Staff and pay",
        required=False,
        help_text="Off: attendance and pay stay private",
    )
    send_invoice = forms.BooleanField(
        label="Send invoice on WhatsApp",
        required=False,
        help_text="Opens WhatsApp with the invoice as text.",
    )
    send_invoice_off = forms.BooleanField(
        label="Send invoice on WhatsApp",
        required=False,
        disabled=True,
        help_text="Add a phone number on S07 first.",
    )
    place = forms.ChoiceField(
        label="Place in queue",
        widget=forms.RadioSelect,
        choices=[("suggested", "Suggested: 6th"), ("next", "Next up")],
    )


class ErrorsForm(forms.Form):
    customer = forms.CharField(
        label="Customer",
        error_messages={"required": "Choose a customer, or add a new one."},
    )
    estimate = forms.CharField(
        label="Your estimate to make it",
        help_text="Usually 3h 10m for an anarkali (last 10).",
        error_messages={"required": "Enter how long it will take, like 2h 30m."},
    )


INITIAL = {
    "due": "Fri 13 Nov 2026",
    "assign": "ali",
    "advance": "1,000",
    "who_pays": "customer",
    "method": "cash",
    "mcp": True,
    "staff_pay": False,
    "send_invoice": True,
    "place": "suggested",
}
PLACE_NOTES = {
    "suggested": "After the chudidar, ready by Tue 17 Nov",
    "next": "Right after the item Ali's on",
}
FILTERS = [
    ("open", "Open", 12),
    ("ready", "Ready", 3),
    ("delivered", "Delivered", None),
    ("free", "Free", None),
]
MEASUREMENTS = [
    {"label": "Bust", "value": "34"},
    {"label": "Waist", "value": "28"},
    {"label": "Shoulder", "value": "14"},
    {"label": "Sleeve length", "value": "11½"},
    {"label": "Armhole", "value": "16"},
    {"label": "Blouse length", "value": "15"},
]


def _row(rank, garment, order, due, time_needed, tone, status, photo, count, **flags):
    return {
        "rank": rank,
        "garment": garment,
        "order_label": order,
        "due_label": due,
        "due_soon": flags.get("due_soon", False),
        "time_needed": time_needed,
        "tone": tone,
        "status": status,
        "moved": flags.get("moved", False),
        "photo": photo,
        "photo_count": count,
        "picked": flags.get("picked", False),
    }


QUEUE = [
    _row(
        1,
        "Blouse",
        "ORD-1042",
        "Due tomorrow",
        "about 1h left",
        "pri",
        "In progress",
        "styleguide/blouse.svg",
        3,
        due_soon=True,
    ),
    _row(
        2,
        "Petticoat",
        "ORD-1042",
        "Due tomorrow",
        "about 1h",
        "warn",
        "Not started",
        None,
        0,
        due_soon=True,
    ),
    _row(
        3,
        "Kurta",
        "ORD-1044",
        "Due Mon 16 Nov",
        "about 2h",
        "warn",
        "Not started",
        "styleguide/kurta.svg",
        1,
        moved=True,
        picked=True,
    ),
    _row(
        4,
        "Chudidar",
        "ORD-1043",
        "Due Mon 16 Nov",
        "about 3h",
        "warn",
        "Not started",
        "styleguide/kurta.svg",
        2,
    ),
]


def _queue() -> list[dict]:
    return [
        {**row, "photo": static(row["photo"]) if row["photo"] else None}
        for row in QUEUE
    ]


def context(status: str | None) -> dict:
    status = status if status in {key for key, _, _ in FILTERS} else "open"
    return {
        "controls": ControlsForm(initial=INITIAL),
        "errors_form": ErrorsForm(data={}, prefix="err"),
        "place_notes": PLACE_NOTES,
        "measurements": MEASUREMENTS,
        "queue": _queue(),
        "queue_total": len(QUEUE),
        "photo_blouse": static("styleguide/blouse.svg"),
        "chips": [
            {
                "label": label,
                "count": count,
                "url": f"?status={key}",
                "selected": key == status,
            }
            for key, label, count in FILTERS
        ],
    }
