import re

import pytest

from catalog.models import Product

# Custom before ready-made, each by name.
SOLD_NAMES = [
    "Blouse",
    "Chudidar",
    "Kurta",
    "Lehenga blouse",
    "Petticoat",
    "Salwar suit",
    "Saree fall and pico",
    "Cotton dupatta",
    "Silk stole",
]


def text_of(response):
    html = response.content.decode()
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def row_names(response):
    html = response.content.decode()
    return re.findall(r'<span class="t-body prow__title">([^<]+)</span>', html)


@pytest.fixture
def get(owner_client, demo_catalog):
    return lambda query="": owner_client.get("/products/" + query)


def test_sold_list(get):
    response = get()
    assert response.status_code == 200
    assert row_names(response) == SOLD_NAMES
    text = text_of(response)
    for label, count in (
        ("Sold", 9),
        ("Materials", 6),
        ("Custom", 7),
        ("Ready-made", 2),
    ):
        assert re.search(rf"{label}\s*\(\s*{count}\s*\)", text)
    assert "3 options: Lining, Sleeve style, Padding" in text
    assert "No options" in text
    assert "₹1,800" in text
    assert "Lining, cotton cream" not in text


def test_materials_list(get):
    response = get("?kind=materials")
    text = text_of(response)
    assert len(row_names(response)) == 6
    for expected in (
        "sells ₹150",
        "not billed on its own",
        "picked by hand",
        "Collar on Kurta",
        "cost a pair",
        "Lining on 4 products",
    ):
        assert expected in text
    assert "Blouse" not in row_names(response)
    assert "fchip" not in response.content.decode()


def test_inactive_hidden(get):
    Product.objects.filter(name__in=["Silk stole", "Saree fall"]).update(active=False)
    response = get()
    text = text_of(response)
    assert "Silk stole" not in row_names(response)
    assert re.search(r"Sold \(\s*8\s*\)", text)
    assert re.search(r"Materials \(\s*5\s*\)", text)
    assert re.search(r"Ready-made \(\s*1\s*\)", text)
    assert "Fall from shop" not in text_of(get("?kind=materials"))


def test_type_chip_filters(get):
    response = get("?type=ready_made")
    assert row_names(response) == ["Cotton dupatta", "Silk stole"]
    assert re.search(
        r'id="chip-ready_made"\s+href="[^"]*"\s+hx-get[^>]*aria-current="true"',
        response.content.decode(),
    )


def test_search(get):
    response = get("?q=BLO")
    assert row_names(response) == ["Blouse", "Lehenga blouse"]
    assert "?q=BLO" in response.content.decode()


def test_search_no_results_escaped(get):
    response = get("?q=<b>sherwani")
    html = response.content.decode()
    assert "&lt;b&gt;sherwani" in html
    assert "<b>sherwani" not in html
    assert "Add it?" in html
    assert "+ Add product" in html


def test_empty_shop(owner_client):
    html = owner_client.get("/products/").content.decode()
    assert "No products yet" in html
    assert "seg__opt" not in html


def test_no_materials(owner_client, demo_catalog):
    Product.objects.filter(kind="secondary").update(active=False)
    html = owner_client.get("/products/?kind=materials").content.decode()
    assert "No materials yet" in html
    assert "Add lining or falls to use on items." in html


def test_chip_with_no_products(owner_client, demo_catalog):
    Product.objects.filter(type="ready_made").update(active=False)
    html = owner_client.get("/products/?type=ready_made").content.decode()
    assert "No ready-made products yet." in html
    assert "fchip" in html


def test_partial_request_returns_fragment(get, owner_client, demo_catalog):
    response = owner_client.get(
        "/products/", headers={"HX-Request": "true", "HX-Request-Type": "partial"}
    )
    html = response.content.decode()
    assert 'id="catalog-results"' in html
    assert 'class="nav"' not in html
