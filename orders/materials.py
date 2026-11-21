"""Material lines on items: rows, picker order, invoice lines (S04, S20)."""

from decimal import Decimal

from catalog.models import ProductOption
from core.formats import format_day
from core.money import format_inr
from orders import finishing, invoice


def format_qty(q: Decimal) -> str:
    text = f"{q:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def qty_label(unit: str) -> str:
    return f"Quantity ({unit})" if unit else "Quantity"


def cost_total(line) -> Decimal | None:
    if line.cost_price is None:
        return None
    return finishing.total_for(line.cost_price, line.quantity)


def line_row(line) -> dict:
    cost = cost_total(line)
    return {
        "pk": line.pk,
        "name": line.name,
        "qty": f"{format_qty(line.quantity)} {line.unit}",
        "on_bill": line.on_bill,
        "bill_label": "On bill" if line.on_bill else "In price",
        "bought": f"Bought {format_day(line.bought_on)}"
        if line.bought_on
        else "Not bought yet",
        "cost": format_inr(cost) if cost is not None else "No cost yet",
        "sell": format_inr(finishing.total_for(line.selling_price, line.quantity)),
    }


def material_choices(products) -> list[dict]:
    return [
        {
            "id": p.pk,
            "name": p.name,
            "unit": p.unit,
            "unitCost": str(p.cost_price),
            "unitSell": str(p.selling_price),
            "billed": p.billed_by_default,
            "sub": f"Cost {format_inr(p.cost_price)} · "
            f"sells {format_inr(p.selling_price)} a {p.unit}",
        }
        for p in products
    ]


def bill_lines(items) -> list[dict]:
    """Each item with its billed materials, for the invoice."""
    lines = []
    for number, item in enumerate(items, start=1):
        billed = [m for m in item.materials.all() if m.on_bill]
        lines.append(
            {
                "number": number,
                "name": item.name,
                "price": item.price,
                "materials": [
                    {
                        "label": f"{m.name} · {format_qty(m.quantity)} {m.unit}",
                        "amount": invoice.material_amount(
                            invoice.Material(m.quantity, m.selling_price, True)
                        ),
                    }
                    for m in billed
                ],
            }
        )
    return lines


def options_to_add(options, answers, material_ids) -> list[ProductOption]:
    """At-order options with a material the item lacks, one per material."""
    found, seen = [], set()
    for o in options:
        if o.material_id in seen:
            continue
        if finishing.needs_answer(
            o, answers, material_ids, when=ProductOption.AT_ORDER
        ):
            seen.add(o.material_id)
            found.append(o)
    return found
