"""Mark ready and Mark delivered: when-done questions and the bottom bar (S04)."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from catalog.models import Product, ProductOption
from core.formats import format_phone
from core.money import format_inr
from orders.forms import PRICE_INVALID
from orders.items import price_input
from orders.models import MaterialLine, Order, OrderItem
from staff.attendance import first_name, parse_decimal

QTY_INVALID = "Enter a quantity above zero, like 0.8."
CENT = Decimal("0.01")
SEND_NO_PHONE = "Add a phone number on S07 first."
WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")


@dataclass(frozen=True)
class Question:
    item: OrderItem
    number: int  # the item's 1-based place on the order
    option: ProductOption  # asked when done, with a material

    @property
    def key(self) -> str:
        return f"{self.item.pk}_{self.option.pk}"


def needs_answer(
    option: ProductOption,
    answers: list[dict],
    material_ids: set,
    when: str = ProductOption.WHEN_DONE,
) -> bool:
    if option.asked_when != when or option.material_id is None:
        return False
    answer = next((a["answer"] for a in answers if a["name"] == option.name), "")
    if option.answer == ProductOption.YES_NO:
        if answer != "Yes":
            return False
    elif not answer:
        return False
    return option.material_id not in material_ids


def pending_questions(order: Order) -> list[Question]:
    items = order.items.select_related("product").prefetch_related(
        "materials", "product__options__material"
    )
    found = []
    for number, item in enumerate(items, start=1):
        if item.product is None or item.type != Product.CUSTOM:
            continue
        ids = {m.product_id for m in item.materials.all()}
        for option in item.product.options.all():
            if needs_answer(option, item.options, ids):
                found.append(Question(item, number, option))
    return found


def unit_label(unit: str) -> str:
    return "Length (m)" if unit == "m" else f"Quantity ({unit})"


def per_unit(total: Decimal, quantity: Decimal) -> Decimal:
    return (total / quantity).quantize(CENT, ROUND_HALF_UP)


def total_for(unit_price: Decimal, quantity: Decimal) -> Decimal:
    return (unit_price * quantity).quantize(CENT, ROUND_HALF_UP)


def question_row(q: Question, data=None) -> dict:
    """The template row for one question: posted values and errors, or defaults."""
    material, item, key = q.option.material, q.item, q.key
    one = Decimal(1)
    row = {
        "key": key,
        "title": f"Item {q.number} · {item.name} · {q.option.name}",
        "sub": (
            f"{material.name} · cost {format_inr(material.cost_price)}, "
            f"sells {format_inr(material.selling_price)} a {material.unit}"
        ),
        "qty_label": unit_label(material.unit),
        "qty": "1",
        "cost": price_input(total_for(material.cost_price, one)),
        "sell": price_input(total_for(material.selling_price, one)),
        "qty_error": "",
        "cost_error": "",
        "sell_error": "",
        "unit_cost": material.cost_price,
        "unit_sell": material.selling_price,
        "note": (
            f"Added to the {item.name.lower()}'s materials and to the bill."
            if material.billed_by_default
            else f"Added to the {item.name.lower()}'s materials, in the price. "
            "Counted in its gain."
        ),
    }
    if data is not None:
        for field in ("qty", "cost", "sell"):
            row[field] = data.get(f"{field}_{key}", "")
        _, errors = clean_answer(row["qty"], row["cost"], row["sell"])
        for field, message in errors.items():
            row[f"{field}_error"] = message
    return row


def _number(raw) -> Decimal | None:
    return parse_decimal(str(raw).replace("₹", "").replace(",", "").replace(" ", ""))


def _too_precise(value: Decimal) -> bool:
    return value.as_tuple().exponent < -2


def clean_answer(
    qty_raw: str, cost_raw: str, sell_raw: str, *, cost_optional: bool = False
) -> tuple[tuple[Decimal, Decimal | None, Decimal] | None, dict]:
    qty, cost, sell = _number(qty_raw), _number(cost_raw), _number(sell_raw)
    blank_cost = cost_optional and str(cost_raw).strip() == ""
    prices = (("sell", sell),) if blank_cost else (("cost", cost), ("sell", sell))
    errors = {}
    if qty is None or qty <= 0 or _too_precise(qty) or qty >= 1_000_000:
        errors["qty"] = QTY_INVALID
    for field, price in prices:
        if price is None or price < 0 or _too_precise(price) or price >= 10**10:
            errors[field] = PRICE_INVALID
    if not errors:  # the saved per-unit price must fit the column too
        for field, price in prices:
            if per_unit(price, qty) >= 10**10:
                errors[field] = PRICE_INVALID
    if errors:
        return None, errors
    return (qty, None if blank_cost else cost, sell), {}


def save_answers(questions: list[Question], data) -> tuple[list[dict], int]:
    """Create the material lines if every answer is valid (inside a transaction)."""
    rows = [question_row(q, data) for q in questions]
    cleaned = []
    count = 0
    for row in rows:
        answer, errors = clean_answer(row["qty"], row["cost"], row["sell"])
        cleaned.append(answer)
        count += len(errors)
    if not count:
        for q, (qty, cost, sell) in zip(questions, cleaned, strict=True):
            MaterialLine.from_product(
                q.option.material,
                qty,
                item=q.item,
                cost_price=per_unit(cost, qty),
                selling_price=per_unit(sell, qty),
            )
    return rows, count


def deliver_confirm(order: Order) -> str:
    invoice = order.invoice()
    if invoice is None or invoice.balance <= 0:
        return ""
    return (
        f"{first_name(order.customer.name)} still owes "
        f"{format_inr(invoice.balance)}. Mark delivered anyway?"
    )


def send_row(order: Order, checked: bool = False) -> dict | None:
    """The Send invoice on WhatsApp row of the Mark ready sheet; None on free orders."""
    inv = order.invoice()
    if inv is None:
        return None
    phone = order.customer.phone
    if not phone:
        return {"disabled": True, "checked": False, "hint": SEND_NO_PHONE}
    balance = "Paid" if inv.paid else f"balance {format_inr(inv.balance)}"
    return {
        "disabled": False,
        "checked": checked,
        "hint": f"{order.customer.name} · {format_phone(phone)} · {balance}",
    }


def bar(order: Order, pending: bool) -> dict:
    """What the bottom bar shows for the order's status."""
    if order.status in (Order.OPEN, Order.IN_PROGRESS):
        return {"action": "ready"}
    if order.status == Order.READY:
        return {
            "action": "deliver",
            "sheet": pending,
            "confirm": deliver_confirm(order),
        }
    return {"action": None}


def things(n: int) -> str:
    word = WORDS[n - 1] if 1 <= n <= len(WORDS) else str(n)
    return f"{word} thing" if n == 1 else f"{word} things"
