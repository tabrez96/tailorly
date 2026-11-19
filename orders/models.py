from django.db import models, transaction
from django.db.models import Max, Q

from catalog.models import Product
from customers.measurements import merge_fields
from customers.models import MeasurementSet
from orders import invoice


class OrderError(ValueError):
    """A status change or payment the order's state doesn't allow."""


class Order(models.Model):
    DRAFT, OPEN, IN_PROGRESS, READY, DELIVERED = (
        "draft",
        "open",
        "in_progress",
        "ready",
        "delivered",
    )
    STATUSES = [
        (DRAFT, "Draft"),
        (OPEN, "Open"),
        (IN_PROGRESS, "In progress"),
        (READY, "Ready"),
        (DELIVERED, "Delivered"),
    ]
    CUSTOMER, FREE = "customer", "free"
    PAID_BY = [(CUSTOMER, "Customer"), (FREE, "Free")]
    TRANSITIONS = {
        DRAFT: {OPEN, DELIVERED},
        OPEN: {IN_PROGRESS, READY},
        IN_PROGRESS: {READY},
        READY: {DELIVERED},
        DELIVERED: set(),
    }

    number = models.PositiveIntegerField(
        null=True, blank=True, unique=True
    )  # given when the draft is placed
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
    paid_by = models.CharField(max_length=8, choices=PAID_BY, default=CUSTOMER)
    assignee = models.ForeignKey(
        "staff.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    invoice_last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    status__in=["draft", "open", "in_progress", "ready", "delivered"]
                ),
                name="order_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(paid_by__in=["customer", "free"]),
                name="order_paid_by_valid",
            ),
            models.CheckConstraint(
                condition=Q(status="draft") | Q(number__isnull=False),
                name="order_number_when_placed",
            ),
        ]

    def __str__(self):
        return f"#{self.number}" if self.number else "Draft order"

    @property
    def is_free(self) -> bool:
        return self.paid_by == self.FREE

    def _move(self, to: str) -> None:
        if to not in self.TRANSITIONS[self.status]:
            raise OrderError(
                f"Can't move a {self.get_status_display().lower()} order "
                f"to {dict(self.STATUSES)[to].lower()}."
            )
        self.status = to
        self.save(update_fields=["status", "number", "due_date", "updated_at"])

    def place(self) -> None:
        with transaction.atomic():
            if self.status != self.DRAFT:
                self._move(self.OPEN)  # raises
            if not self.items.exists():
                raise OrderError("Add at least one item.")
            # A ready-made sale is saved as Delivered.
            all_ready_made = not self.items.filter(type=Product.CUSTOM).exists()
            target = self.DELIVERED if all_ready_made else self.OPEN
            if target == self.OPEN and self.due_date is None:
                raise OrderError("Choose a due date.")
            self.number = (Order.objects.aggregate(n=Max("number"))["n"] or 0) + 1
            self._move(target)

    def start_work(self) -> None:
        if self.status == self.IN_PROGRESS:
            return
        self._move(self.IN_PROGRESS)

    def mark_ready(self) -> None:
        self._move(self.READY)

    def mark_delivered(self) -> None:
        # A draft only reaches Delivered through place(), which numbers it first.
        if self.status != self.READY:
            raise OrderError(
                f"Can't move a {self.get_status_display().lower()} order to delivered."
            )
        self._move(self.DELIVERED)

    def record_payment(self, amount, date, method) -> Payment:
        if self.is_free:
            raise OrderError("Free orders have no payments.")
        if self.status == self.DRAFT:
            raise OrderError("Place the order before taking a payment.")
        if amount <= 0:
            raise OrderError("Enter an amount above zero.")
        return self.payments.create(amount=amount, date=date, method=method)

    def invoice(self) -> invoice.Invoice | None:
        if self.is_free:
            return None
        items = [
            invoice.Item(
                i.price,
                tuple(
                    invoice.Material(m.quantity, m.selling_price, m.on_bill)
                    for m in i.materials.all()
                ),
            )
            for i in self.items.prefetch_related("materials")
        ]
        return invoice.build(items, [p.amount for p in self.payments.all()])


class OrderItem(models.Model):
    NOT_STARTED, IN_PROGRESS, FINISHED = "not_started", "in_progress", "finished"
    STATUSES = [
        (NOT_STARTED, "Not started"),
        (IN_PROGRESS, "In progress"),
        (FINISHED, "Finished"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # Link only (usual time, measurement set); what is shown comes from the copies.
    product = models.ForeignKey(
        "catalog.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_items",
    )
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=10, choices=Product.TYPES)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    usual_price = models.DecimalField(max_digits=12, decimal_places=2)
    # [{"name": "Lining", "answer": "Yes"}, ...]
    options = models.JSONField(default=list, blank=True)
    # Own copy: [{"name": "Bust", "value": "34.5"}, ...], inches.
    measurements = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default=NOT_STARTED)
    estimate_minutes = models.PositiveIntegerField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=0), name="item_price_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(usual_price__gte=0), name="item_usual_price_not_negative"
            ),
            models.CheckConstraint(
                condition=Q(type__in=["custom", "ready_made"]), name="item_type_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=["not_started", "in_progress", "finished"]),
                name="item_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(type="custom") | Q(measurements=[]),
                name="item_measurements_custom_only",
            ),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def from_product(cls, order, product, answers=()) -> OrderItem:
        """Add an item that copies the product (and, if custom, measurements)."""
        measurements = []
        if product.type == Product.CUSTOM:
            saved = MeasurementSet.objects.filter(
                customer=order.customer, product=product
            ).first()
            rows = merge_fields(
                product.measurement_fields, saved.values if saved else []
            )
            measurements = [{"name": r.name, "value": r.value} for r in rows]
        return cls.objects.create(
            order=order,
            product=product,
            name=product.name,
            type=product.type,
            price=product.usual_price,
            usual_price=product.usual_price,
            options=[dict(a) for a in answers],
            measurements=measurements,
            position=order.items.count(),
        )


class ItemPhoto(models.Model):
    # The first photo is the item's picture everywhere.
    item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="orders/")
    thumb = models.ImageField(upload_to="orders/thumbs/")
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Photo of {self.item}"


class Rework(models.Model):
    FIT, MISTAKE, CHANGE, REPAIR = "fit", "mistake", "change", "repair"
    REASONS = [
        (FIT, "Fit alteration"),
        (MISTAKE, "Our mistake"),
        (CHANGE, "Customer change"),
        (REPAIR, "Repair"),
    ]

    item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name="reworks"
    )
    reason = models.CharField(max_length=8, choices=REASONS)
    note = models.TextField(blank=True)
    assignee = models.ForeignKey(
        "staff.Employee",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reworks",
    )
    estimate_minutes = models.PositiveIntegerField(default=45)
    due_date = models.DateField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(reason__in=["fit", "mistake", "change", "repair"]),
                name="rework_reason_valid",
            ),
        ]

    def __str__(self):
        return f"{self.get_reason_display()}: {self.item}"


class MaterialLine(models.Model):
    item = models.ForeignKey(
        OrderItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    rework = models.ForeignKey(
        Rework,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="materials",
    )
    product = models.ForeignKey(
        "catalog.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="material_lines",
    )
    name = models.CharField(max_length=80)
    unit = models.CharField(max_length=4, choices=Product.UNITS)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    # Per unit; filled in later when unknown.
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)  # per unit
    on_bill = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(item__isnull=False, rework__isnull=True)
                | Q(item__isnull=True, rework__isnull=False),
                name="material_line_one_owner",
            ),
            models.CheckConstraint(
                condition=Q(rework__isnull=True) | Q(on_bill=False),
                name="rework_material_never_billed",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="material_quantity_positive"
            ),
            models.CheckConstraint(
                condition=Q(cost_price__isnull=True) | Q(cost_price__gte=0),
                name="material_cost_not_negative",
            ),
            models.CheckConstraint(
                condition=Q(selling_price__gte=0), name="material_selling_not_negative"
            ),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def from_product(cls, product, quantity, *, item=None, rework=None) -> MaterialLine:
        """Copy the material; reworks are never billed."""
        return cls.objects.create(
            item=item,
            rework=rework,
            product=product,
            name=product.name,
            unit=product.unit,
            quantity=quantity,
            cost_price=product.cost_price,
            selling_price=product.selling_price,
            on_bill=product.billed_by_default and rework is None,
        )


class Payment(models.Model):
    CASH, UPI, CARD, BANK = "cash", "upi", "card", "bank"
    METHODS = [(CASH, "Cash"), (UPI, "UPI"), (CARD, "Card"), (BANK, "Bank")]

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    method = models.CharField(max_length=4, choices=METHODS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payment_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(method__in=["cash", "upi", "card", "bank"]),
                name="payment_method_valid",
            ),
        ]

    def __str__(self):
        return f"{self.amount} ({self.get_method_display()})"
