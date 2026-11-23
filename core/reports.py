"""The row of report chips shared by the report pages."""

from django.urls import NoReverseMatch, reverse

REPORTS = [
    ("Sales", "sales_report"),
    ("Profit", "profit_report"),
    ("Production", "production_report"),
    ("Payments", "payments_report"),
    ("Staff", "staff_report"),
]


def report_row(current: str, query: str = "") -> list[dict]:
    """One chip per report whose page exists; the current one selected."""
    chips = []
    for label, name in REPORTS:
        try:
            url = reverse(name)
        except NoReverseMatch:
            continue
        chips.append(
            {
                "id": f"report-{name}",
                "label": label,
                "url": f"{url}?{query}" if query else url,
                "selected": name == current,
            }
        )
    return chips
