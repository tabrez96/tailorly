from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from customers.models import Customer
from orders.models import Order, Payment
from production.live import GONE, IDLE, NOT_IN, PAUSED, WORKING
from production.models import TimeSession
from reports import payments
from staff.attendance import week_start
from staff.models import DayRecord
from staff.pay import week_pay
from today import cards

URLS = {"employee": "/e/", "customer": "/c/", "order": "/o/"}


def aware(y, m, d, h=9, mi=0):
    return timezone.make_aware(datetime(y, m, d, h, mi))


def test_overline_with_and_without_name():
    now = aware(2026, 11, 12)
    assert cards.overline(now, "Sabreen Khan") == "THU 12 NOV · HI SABREEN"
    assert cards.overline(now, "") == "THU 12 NOV"


def test_hero_day_line_states():
    day = {"start": aware(2026, 11, 12, 9, 2), "end": aware(2026, 11, 12, 18, 10)}
    assert cards.hero_day_line(NOT_IN, day) == "Not started yet"
    assert cards.hero_day_line(GONE, day) == "Day 9:02 am – 6:10 pm"
    day["so_far"] = 378
    assert cards.hero_day_line(WORKING, day) == "Day started 9:02 am · 6h 18m so far"


def test_hero_now_working_paused_none():
    item = {
        "order_number": 7,
        "name": "Blouse",
        "customer": "Meera Iyer",
        "minutes_text": "1h 25m",
        "rework": False,
        "base_seconds": 60,
        "started_at": "t",
        "estimate": 90,
    }
    now = cards.hero_now({"state": WORKING, "item": item})
    assert now["label"] == "Now" and now["what"] == "#7 Blouse"
    assert now["timer"] and now["base_seconds"] == 60 and now["estimate"] == 90
    paused = cards.hero_now({"state": PAUSED, "item": {**item, "rework": True}})
    assert paused["label"] == "Paused"
    assert paused["what"] == "Rework · #7 Blouse"
    assert not paused["timer"] and "base_seconds" not in paused
    assert cards.hero_now({"state": IDLE, "item": None}) is None


def test_hero_cards_urls_by_state(ali, make_item):
    item = make_item(ali, due=timezone.localdate())
    [card] = cards.hero_cards(timezone.now())
    assert card["state"] == NOT_IN
    assert card["start_url"] and not card["end_url"]

    record = DayRecord.objects.create(
        employee=ali,
        date=timezone.localdate(),
        start=timezone.now() - timedelta(hours=3),
    )
    [card] = cards.hero_cards(timezone.now())
    assert card["state"] == IDLE
    assert card["end_url"] and not card["start_url"]

    now = timezone.now()
    TimeSession.objects.create(
        employee=ali, item=item, started_at=now - timedelta(minutes=5)
    )
    [card] = cards.hero_cards(now)
    assert card["state"] == WORKING and card["end_url"]
    assert card["now_line"]["timer"]

    TimeSession.objects.update(ended_at=now - timedelta(minutes=1))
    [card] = cards.hero_cards(now)
    assert card["state"] == PAUSED and card["end_url"]

    record.end = now
    record.save()
    [card] = cards.hero_cards(now)
    assert card["state"] == GONE
    assert not card["start_url"] and not card["end_url"]


def test_work_plan_card_lines(ali, make_item, started_day):
    assert cards.work_plan_card(timezone.now()) == {
        "line": "Every order is assigned",
        "chip": "",
        "url": "/production/plan/",
    }
    make_item(ali, due=timezone.localdate())
    make_item(None, name="Anarkali")
    make_item(None, name="Saree")
    plan = cards.work_plan_card(timezone.now())
    assert plan["line"] == "2 orders not assigned · Ali's next: Blouse"
    assert plan["chip"] == "Assign 2"


def test_due_rows_window_and_order(ali, make_item):
    today = timezone.localdate()

    def mk(days, status="open", **kw):
        due = None if days is None else today + timedelta(days=days)
        return make_item(ali, due=due, status=status, **kw).order

    plus3 = mk(3)
    done = mk(0, "delivered")
    stale_ready = mk(-1, "ready")
    nodue = mk(None)
    tomorrow = mk(1)
    ready_today = mk(0, "ready")
    plus2 = mk(2)
    late = mk(-3)
    today_o = mk(0, "in_progress")
    rows = cards.due_rows(today)
    got = [r["order"].pk for r in rows]
    assert got == [late.pk, ready_today.pk, today_o.pk, tomorrow.pk, plus2.pk]
    for gone in (plus3, done, stale_ready, nodue):
        assert gone.pk not in got
    assert "Late · was due" in rows[0]["line"] and rows[0]["late"]
    assert rows[3]["line"].endswith("Due tomorrow")


def test_money_matches_payments_report(ali, make_item):
    today = date(2026, 11, 12)  # a Thursday
    monday = week_start(today)
    a = make_item(ali, price="1000").order
    b = make_item(ali, price="500").order
    Payment.objects.create(order=a, amount=Decimal("300"), date=monday, method="cash")
    Payment.objects.create(order=b, amount=Decimal("200"), date=today, method="cash")
    Payment.objects.create(
        order=b,
        amount=Decimal("50"),
        date=monday - timedelta(days=1),
        method="cash",
    )
    m = cards.money(today)
    c = payments.collect(payments.load_owing())
    assert m["collect_total"] == c["total"]
    assert m["collect_count_text"] == f"{c['orders']} orders"
    assert m["received"] == Decimal("500")
    assert m["received_range"] == "Mon 9 – today"
    assert cards.money(monday)["received_range"] == "Today"
    assert m["collect_url"] == "/orders/?show=owing"
    assert m["received_url"] == "/reports/payments/?period=week"


def test_staff_pay_matches_week_pay(ali):
    today = date(2026, 11, 12)
    monday = week_start(today)
    for offset in (0, 1):
        day = monday + timedelta(days=offset)
        DayRecord.objects.create(
            employee=ali,
            date=day,
            start=aware(day.year, day.month, day.day, 9),
            end=aware(day.year, day.month, day.day, 17),
        )
    ali.refresh_from_db()
    records = {
        r.date: (r.start, r.end) for r in ali.days.filter(date__range=(monday, today))
    }
    week = week_pay(monday, records, ali.daily_wage, ali.overtime_multiplier, today)
    [row] = cards.staff_pay(today)
    assert row["total"] == week.total
    assert row["line"] == "This week so far · 2 days"
    assert row["url"] == f"/settings/staff/?e={ali.pk}"


def test_settings_url_empty_without_route():
    assert cards.settings_url() == ""


def test_setup_steps_none_done():
    steps = cards.setup_steps(False, False, URLS)
    assert [s["done"] for s in steps] == [False] * 3
    assert [s["primary"] for s in steps] == [True, False, False]
    assert [s["label"] for s in steps] == ["Add", "Add", "Create"]
    assert [s["url"] for s in steps] == ["/e/", "/c/", "/o/"]


def test_setup_steps_employee_done():
    steps = cards.setup_steps(True, False, URLS)
    assert steps[0]["done"] and not steps[0]["primary"]
    assert [s["primary"] for s in steps] == [False, True, False]


def test_setup_steps_both_done():
    steps = cards.setup_steps(True, True, URLS)
    assert [s["done"] for s in steps] == [True, True, False]
    assert [s["primary"] for s in steps] == [False, False, True]


def test_is_first_run_ignores_drafts(db):
    customer = Customer.objects.create(name="Meera Iyer", phone="9000000011")
    Order.objects.create(customer=customer, number=1, status=Order.DRAFT)
    assert cards.is_first_run()
    Order.objects.create(customer=customer, number=2, status=Order.OPEN)
    assert not cards.is_first_run()
