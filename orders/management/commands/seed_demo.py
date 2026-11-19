from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Product, ProductOption
from customers.models import Customer, MeasurementSet
from orders.models import MaterialLine, Order, OrderItem, Payment, Rework
from staff.models import Employee


def _material(name, unit, cost, selling, billed):
    return Product.objects.get_or_create(
        name=name,
        kind=Product.SECONDARY,
        defaults={
            "unit": unit,
            "cost_price": Decimal(cost),
            "selling_price": Decimal(selling),
            "billed_by_default": billed,
        },
    )[0]


def _garment(name, type, price, fields=()):
    return Product.objects.get_or_create(
        name=name,
        kind=Product.PRIMARY,
        defaults={
            "type": type,
            "usual_price": Decimal(price),
            "measurement_fields": list(fields),
        },
    )[0]


def _order(customer, products, *, due=None, assignee=None, paid_by=Order.CUSTOMER):
    order = Order.objects.create(
        customer=customer, due_date=due, assignee=assignee, paid_by=paid_by
    )
    items = [OrderItem.from_product(order, p) for p in products]
    return order, items


def _finish(order):
    order.items.update(status=OrderItem.FINISHED)


class Command(BaseCommand):
    help = (
        "Fill an empty shop with generic demo data: products, customers, an employee "
        "and orders in every status."
    )

    def handle(self, *args, **options):
        if Order.objects.exists():
            self.stdout.write("Orders already exist; demo data not added.")
            return
        with transaction.atomic():
            self._seed()
        self.stdout.write(f"Demo shop ready: {Order.objects.count()} orders.")

    def _seed(self):
        today = timezone.localdate()
        day = timedelta

        lining = _material("Lining, cotton", "m", "60", "90", True)
        fall = _material("Fall", "pcs", "25", "40", False)
        blouse = _garment(
            "Blouse",
            Product.CUSTOM,
            "1200",
            ["Bust", "Waist", "Shoulder", "Sleeve length"],
        )
        chudidar = _garment(
            "Chudidar", Product.CUSTOM, "900", ["Waist", "Hip", "Length"]
        )
        kurta = _garment("Cotton kurta", Product.READY_MADE, "799")
        if not blouse.options.exists():
            ProductOption.objects.create(
                product=blouse,
                name="Lining",
                answer=ProductOption.YES_NO,
                material=lining,
                asks_quantity=True,
            )

        ravi = Employee.objects.get_or_create(
            phone="9000000001",
            defaults={"name": "Ravi Kumar", "daily_wage": Decimal("800")},
        )[0]
        asha, neha, kavya = (
            Customer.objects.get_or_create(phone=phone, defaults={"name": name})[0]
            for name, phone in [
                ("Asha Rao", "9000000011"),
                ("Neha Singh", "9000000012"),
                ("Kavya Menon", "9000000013"),
            ]
        )
        MeasurementSet.objects.get_or_create(
            customer=asha,
            product=blouse,
            defaults={
                "values": [
                    {"name": "Bust", "value": "34"},
                    {"name": "Waist", "value": "28"},
                    {"name": "Shoulder", "value": "14"},
                    {"name": "Sleeve length", "value": "10"},
                ]
            },
        )

        # 1. Draft
        _order(neha, [chudidar], due=today + day(10))

        # 2. Open
        order, (item,) = _order(asha, [blouse], due=today + day(7), assignee=ravi)
        item.options = [{"name": "Lining", "answer": "Yes"}]
        item.save(update_fields=["options"])
        MaterialLine.from_product(lining, Decimal("1.5"), item=item)
        order.place()
        order.record_payment(Decimal("500"), today, Payment.UPI)

        # 3. In progress
        order, items = _order(
            kavya, [blouse, chudidar], due=today + day(3), assignee=ravi
        )
        order.place()
        order.start_work()
        items[0].status = OrderItem.IN_PROGRESS
        items[0].save(update_fields=["status"])

        # 4. Ready
        order, _ = _order(neha, [blouse], due=today + day(1), assignee=ravi)
        order.place()
        order.start_work()
        _finish(order)
        order.mark_ready()
        order.record_payment(Decimal("600"), today, Payment.CASH)

        # 5. Delivered, with a rework
        order, (item,) = _order(asha, [chudidar], due=today - day(5), assignee=ravi)
        MaterialLine.from_product(fall, 1, item=item)
        order.place()
        order.start_work()
        _finish(order)
        order.mark_ready()
        order.mark_delivered()
        order.record_payment(order.invoice().total, today, Payment.CARD)
        rework = Rework.objects.create(
            item=item, reason=Rework.FIT, assignee=ravi, due_date=today + day(2)
        )
        MaterialLine.from_product(lining, Decimal("0.5"), rework=rework)

        # 6. Ready-made sale (placed straight to Delivered)
        order, _ = _order(kavya, [kurta])
        order.place()
        order.record_payment(Decimal("799"), today, Payment.UPI)

        # 7. Free order
        order, _ = _order(
            asha, [blouse], due=today + day(14), assignee=ravi, paid_by=Order.FREE
        )
        order.place()
