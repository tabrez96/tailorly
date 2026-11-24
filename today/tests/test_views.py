from datetime import timedelta

from django.utils import timezone

from production.models import TimeSession
from staff.models import DayRecord


def test_today_links(owner, ali, make_item):
    item = make_item(ali, due=timezone.localdate() + timedelta(days=1))
    html = owner.get("/").content.decode()
    for href in (
        f"/orders/{item.order.pk}/",
        "/production/plan/",
        "/production/report/?from=today",
        "/orders/?show=owing",
        "/reports/payments/?period=week",
        f"/settings/staff/?e={ali.pk}",
    ):
        tag = html[html.index(f'href="{href}"') :].split(">", 1)[0]
        assert 'hx-target="#page"' in tag and 'hx-push-url="true"' in tag, href
    assert "Hi SABREEN" not in html and "· HI SABREEN" in html


def test_no_gear_without_settings_route(owner):
    assert 'aria-label="Settings"' not in owner.get("/").content.decode()


def test_no_heroes_without_employees(owner):
    html = owner.get("/").content.decode()
    assert 'id="today-hero"' not in html
    assert "Staff pay" not in html


def test_nothing_due_text(owner):
    assert "Nothing due in the next 2 days." in owner.get("/").content.decode()


def test_hero_fragment(owner, ali):
    html = owner.get("/today/hero/").content.decode()
    assert 'id="today-hero"' in html and "Ali Khan" in html
    assert "livePoll('/today/hero/', 30000, '#today-hero')" in html
    assert "<html" not in html


def test_end_day_same_as_s10(owner, ali, make_item):
    item = make_item(ali)
    DayRecord.objects.create(
        employee=ali,
        date=timezone.localdate(),
        start=timezone.now() - timedelta(hours=3),
    )
    TimeSession.objects.create(
        employee=ali, item=item, started_at=timezone.now() - timedelta(minutes=5)
    )
    response = owner.post(f"/today/employees/{ali.pk}/day/end/")
    assert "Gone home" in response.content.decode()
    record = DayRecord.objects.get(employee=ali)
    assert record.end and record.edited_by_owner
    assert not TimeSession.objects.filter(ended_at__isnull=True).exists()
    # a second post is harmless
    assert owner.post(f"/today/employees/{ali.pk}/day/end/").status_code == 200


def test_start_day(owner, ali):
    url = f"/today/employees/{ali.pk}/day/start/"
    response = owner.post(url)
    assert "End Ali&#x27;s day" in response.content.decode() or (
        "End Ali's day" in response.content.decode()
    )
    assert DayRecord.objects.get(employee=ali, date=timezone.localdate()).start
    owner.post(url)
    assert DayRecord.objects.filter(employee=ali).count() == 1


def test_start_end_require_post_and_owner(owner, ali):
    for action in ("start", "end"):
        url = f"/today/employees/{ali.pk}/day/{action}/"
        assert owner.get(url).status_code == 405
        assert ali.client.post(url).status_code in (302, 403)
        assert owner.post(f"/today/employees/999/day/{action}/").status_code == 404
    ali.active = False
    ali.save()
    assert owner.post(f"/today/employees/{ali.pk}/day/start/").status_code == 404
