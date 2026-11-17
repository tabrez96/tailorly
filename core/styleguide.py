"""Demo forms and sample data for the styleguide page only."""

from django import forms


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


def context(status: str | None) -> dict:
    status = status if status in {key for key, _, _ in FILTERS} else "open"
    return {
        "controls": ControlsForm(initial=INITIAL),
        "errors_form": ErrorsForm(data={}, prefix="err"),
        "place_notes": PLACE_NOTES,
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
