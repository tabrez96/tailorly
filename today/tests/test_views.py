from datetime import timedelta

from django.utils import timezone

from production.models import TimeSession
from reports.models import ShopSettings
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


def test_gear_opens_settings(owner):
    html = owner.get("/").content.decode()
    tag = html[html.index('aria-label="Settings"') :]
    tag = (
        html[: html.index('aria-label="Settings"')].rsplit("<a", 1)[1]
        + tag.split(">", 1)[0]
    )
    for attr in (
        'href="/settings/"',
        'hx-get="/settings/"',
        'hx-target="#page"',
        'hx-push-url="true"',
    ):
        assert attr in tag, attr


def test_no_heroes_without_employees(owner):
    html = owner.get("/").content.decode()
    assert 'id="today-hero"' not in html
    assert "Staff pay" not in html


def test_nothing_due_text(owner, ali, make_item):
    make_item(ali, due=timezone.localdate() + timedelta(days=30))
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


def test_first_run_shows_setup(owner):
    html = owner.get("/").content.decode()
    assert "Welcome to Tailorly" in html
    assert "You can do these in any order." in html
    assert "Due in the next 2 days" not in html
    assert 'id="hold-tip"' not in html


def step(html, n):
    return html.split(f'id="setup-{n}"')[1].split("</li>")[0]


def test_setup_links_open_in_place(owner):
    html = owner.get("/").content.decode()
    for n, url in (
        (1, "/settings/staff/add/"),
        (2, "/customers/?add=1"),
        (3, "/orders/new/"),
    ):
        part = step(html, n)
        assert f'href="{url}"' in part and f'hx-get="{url}"' in part
        assert 'hx-target="#page"' in part and 'hx-push-url="true"' in part


def test_setup_done_step_has_no_button(owner, ali):
    html = owner.get("/").content.decode()
    one = step(html, 1)
    assert "Done" in one and "<a" not in one
    assert "btn--primary" in step(html, 2)
    assert "btn--tonal" in step(html, 3)


def test_setup_customer_only(owner, customer):
    html = owner.get("/").content.decode()
    assert "btn--primary" in step(html, 1)
    assert "Done" in step(html, 2)


def test_hold_tip_shows_until_got_it(owner, ali, make_item):
    make_item(ali)
    assert 'id="hold-tip"' in owner.get("/").content.decode()
    response = owner.post("/today/hold-tip/", HTTP_HX_REQUEST="true")
    assert response.status_code == 200 and response.content == b""
    assert 'id="hold-tip"' not in owner.get("/").content.decode()
    assert ShopSettings.objects.get(pk=1).hold_tip_seen


def test_hold_tip_not_shown_when_seen_row_exists(owner, ali, make_item):
    make_item(ali)
    ShopSettings.objects.create(pk=1, hold_tip_seen=True)
    assert 'id="hold-tip"' not in owner.get("/").content.decode()


def test_hold_tip_post_without_htmx_redirects(owner):
    response = owner.post("/today/hold-tip/")
    assert response.status_code == 303 and response["Location"] == "/"


def test_hold_tip_owner_only(owner, ali):
    assert ali.client.post("/today/hold-tip/").status_code in (302, 403)
    assert not ShopSettings.objects.exists()
    assert owner.get("/today/hold-tip/").status_code == 405


def test_hold_tip_keeps_costs_unsaved(owner):
    owner.post("/today/hold-tip/", HTTP_HX_REQUEST="true")
    assert not ShopSettings.objects.get(pk=1).costs_saved
