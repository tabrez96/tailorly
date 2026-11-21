from decimal import Decimal as D

from orders import invoice
from orders.invoice import Item, Material, build, item_total, material_amount


def test_total_is_item_prices():
    result = build([Item(D("1200")), Item(D("900"))], [])
    assert result.total == D("2100")


def test_billed_material_adds_selling_price():
    item = Item(D("1200"), (Material(D("1.5"), D("90"), True),))
    assert item_total(item) == D("1200") + D("135.00")


def test_unbilled_material_adds_nothing():
    item = Item(D("1200"), (Material(D("1.5"), D("90"), False),))
    assert item_total(item) == D("1200")


def test_material_amount_rounds_half_up():
    assert material_amount(Material(D("0.33"), D("10.05"), True)) == D("3.32")
    # 5.025 is a true half: half-up gives 5.03, half-even would give 5.02
    assert material_amount(Material(D("0.50"), D("10.05"), True)) == D("5.03")


def test_balance_after_payments():
    result = build([Item(D("1200")), Item(D("900"))], [D("500"), D("600")])
    assert (result.received, result.balance, result.paid) == (
        D("1100"),
        D("1000"),
        False,
    )


def test_paid_when_balance_zero():
    result = build([Item(D("2100"))], [D("2100")])
    assert result.balance == 0
    assert result.paid


def test_overpaid_is_paid_with_negative_balance():
    result = build([Item(D("100"))], [D("150")])
    assert result.balance == D("-50")
    assert result.paid


def test_no_payments_means_not_paid():
    result = build([Item(D("100"))], [])
    assert (result.received, result.balance, result.paid) == (0, D("100"), False)


def test_free_order_has_no_invoice():
    assert build([Item(D("100"))], [], free=True) is None
    assert isinstance(build([], []), invoice.Invoice)


LINES = [
    {
        "number": 1,
        "name": "Blouse",
        "price": D("1800"),
        "materials": [{"label": "Lining · 1 m", "amount": D("150")}],
    },
    {"number": 2, "name": "Petticoat", "price": D("600"), "materials": []},
]


def text(total="2550", received="0", shop="Asha Tailors", number=7, lines=LINES):
    inv = invoice.Invoice(D(total), D(received), D(total) - D(received))
    return invoice.whatsapp_text(shop, number, lines, inv)


def test_whatsapp_text_with_billed_materials():
    assert text().split("\n")[:8] == [
        "Asha Tailors",
        "Invoice for order #7",
        "",
        "1. Blouse: ₹1,800",
        "   + Lining · 1 m: ₹150",
        "2. Petticoat: ₹600",
        "",
        "Total: ₹2,550",
    ]


def test_whatsapp_text_part_payment():
    body = text(received="1000")
    assert "Received: ₹1,000" in body and "Balance: ₹1,550" in body
    assert "Paid" not in body


def test_whatsapp_text_paid():
    body = text(received="2550")
    assert body.endswith("\nPaid") and "Balance" not in body


def test_whatsapp_text_indian_grouping():
    assert "Total: ₹1,42,600" in text(total="142600")


def test_whatsapp_text_blank_shop_name():
    assert text(shop="  ").split("\n")[0] == "Invoice for order #7"


def test_whatsapp_url_encodes():
    from urllib.parse import unquote

    message = "Total: ₹1\n#7 & more"
    url = invoice.whatsapp_url("9845022110", message)
    assert url.startswith("https://wa.me/919845022110?text=")
    assert "%0A" in url and "%23" in url and "%E2%82%B9" in url and "&" not in url[30:]
    assert unquote(url.split("?text=")[1]) == message
