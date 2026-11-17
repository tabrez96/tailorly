from datetime import UTC, date, datetime

from django.template import Context, Template


def test_filters_render_without_load():
    template = Template("{{ a|inr }} {{ d|day }} {{ t|clock }} {{ m|duration }}")
    context = Context(
        {
            "a": 142600,
            "d": date(2026, 11, 12),
            "t": datetime(2026, 11, 12, 3, 32, tzinfo=UTC),
            "m": 160,
        }
    )
    assert template.render(context) == "₹1,42,600 Thu 12 Nov 9:02 am 2h 40m"
