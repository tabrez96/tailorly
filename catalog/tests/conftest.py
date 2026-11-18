import pytest
from django.contrib.auth.models import User

from accounts.roles import OWNER, add_to_role
from catalog.models import Product, ProductOption


@pytest.fixture
def owner_client(client, db):
    user = User.objects.create_user("owner", password="x")
    add_to_role(user, OWNER)
    client.force_login(user)
    return client


def material(name, unit, cost, sells, billed=True):
    return Product.objects.create(
        name=name,
        kind="secondary",
        unit=unit,
        cost_price=cost,
        selling_price=sells,
        billed_by_default=billed,
    )


def garment(name, type_, price, options=()):
    product = Product.objects.create(
        name=name, kind="primary", type=type_, usual_price=price
    )
    for position, (option, mat, *rest) in enumerate(options):
        ProductOption.objects.create(
            product=product,
            name=option,
            material=mat,
            position=position,
            **(rest[0] if rest else {}),
        )
    return product


@pytest.fixture
def demo_catalog(db):
    lining = material("Lining, cotton cream", "m", 120, 150)
    canvas = material("Canvas interlining", "m", 80, 100)
    net = material("Can-can net", "m", 90, 120)
    fall = material("Saree fall", "pcs", 60, 80)
    cups = material("Padding cups", "pair", 70, 100)
    material("Hooks and tape", "set", 90, 0, billed=False)
    sleeve = {"answer": "choice", "choices": ["Short", "Elbow", "Full", "Sleeveless"]}
    garment(
        "Blouse",
        "custom",
        1800,
        [("Lining", lining), ("Sleeve style", None, sleeve), ("Padding", cups)],
    )
    garment("Chudidar", "custom", 1600, [("Lining", lining)])
    garment("Salwar suit", "custom", 2200, [("Lining", lining), ("Pockets", None)])
    garment("Lehenga blouse", "custom", 2800, [("Lining", lining), ("Can-can", net)])
    garment("Kurta", "custom", 1200, [("Collar", canvas)])
    garment("Petticoat", "custom", 600)
    garment("Saree fall and pico", "custom", 250, [("Fall from shop", fall)])
    garment("Cotton dupatta", "ready_made", 450)
    garment("Silk stole", "ready_made", 900)
