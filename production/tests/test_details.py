import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from production.details import details_context
from production.tests.conftest import PARTIAL
from production.tests.test_views import assert_no_money

pytestmark = pytest.mark.django_db

SIZES = [{"name": "Bust", "value": "34"}, {"name": "Waist", "value": "28"}]


@pytest.fixture
def item(ali, make_item, blouse, add_photos):
    blouse.measurement_fields = ["Bust", "Waist"]
    blouse.save()
    item = make_item(ali, estimate=90)
    item.measurements = SIZES
    item.notes = "Hand-finish the hem"
    item.save()
    add_photos(item, 3)
    return item


def get(client, url):
    return client.get(url, headers=PARTIAL)


def test_details_context_photos_and_tiles(item):
    ctx = details_context(item)
    assert [p["alt"] for p in ctx["photos"]] == [
        "Blouse, photo 1 of 3",
        "Blouse, photo 2 of 3",
        "Blouse, photo 3 of 3",
    ]
    assert ctx["tiles"] == [
        {"label": "Bust", "value": "34"},
        {"label": "Waist", "value": "28"},
    ]
    assert ctx["title"] == "#1 · Blouse"


def test_item_details_sheet_renders(ali, item):
    response = get(ali.client, f"/my-work/items/{item.pk}/details/")
    html = response.content.decode()
    assert response.status_code == 200
    for text in [
        "#1 · Blouse",
        "Meera Iyer",
        "1 of 3",
        "Bust",
        "34",
        "Hand-finish the hem",
        "Close",
    ]:
        assert text in html
    assert html.count("thumb--sm") == 3


def test_item_details_without_photos(ali, make_item):
    item = make_item(ali)
    html = get(ali.client, f"/my-work/items/{item.pk}/details/").content.decode()
    assert "thumb--empty" in html
    assert " of " not in html.split("sheet-title")[0]


def test_item_details_404_for_other_employee(ali, make_item):
    from staff.models import Employee

    other = Employee.objects.create(name="Sam", phone="9000011118", daily_wage=800)
    item = make_item(other)
    assert get(ali.client, f"/my-work/items/{item.pk}/details/").status_code == 404


def test_item_details_404_for_unassigned_order(ali, make_item):
    item = make_item(None)
    assert get(ali.client, f"/my-work/items/{item.pk}/details/").status_code == 404


def test_rework_details_sheet(ali, item, make_rework):
    rework = make_rework(item, ali)
    html = get(ali.client, f"/my-work/reworks/{rework.pk}/details/").content.decode()
    for text in [
        "Rework · Blouse",
        "Fit alteration",
        "What to do",
        "Loosen waist by 1 inch",
        "1 of 3",
        "Bust",
        "34",
    ]:
        assert text in html


def test_rework_details_404_for_other_employee(ali, item, make_rework):
    from staff.models import Employee

    other = Employee.objects.create(name="Sam", phone="9000011118", daily_wage=800)
    rework = make_rework(item, other)
    assert get(ali.client, f"/my-work/reworks/{rework.pk}/details/").status_code == 404


def test_details_sheet_has_no_money(ali, item, make_rework):
    from orders.models import MaterialLine

    rework = make_rework(item, ali)
    MaterialLine.objects.create(
        rework=rework,
        name="Lining",
        unit="m",
        quantity=1,
        cost_price=7315,
        selling_price=8642,
    )
    for url in [
        f"/my-work/items/{item.pk}/details/",
        f"/my-work/reworks/{rework.pk}/details/",
    ]:
        assert_no_money(get(ali.client, url).content.decode(), url)


def test_details_requires_employee(item, make_rework, ali):
    owner = User.objects.create_user("owner", password="x")
    owner.groups.add(Group.objects.get_or_create(name="owner")[0])
    client = Client()
    client.force_login(owner)
    response = get(client, f"/my-work/items/{item.pk}/details/")
    assert response.status_code in (302, 403, 404)
