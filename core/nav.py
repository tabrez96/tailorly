from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str
    href: str


OWNER_NAV = (
    NavItem("today", "Today", "house", "/"),
    NavItem("orders", "Orders", "list", "/orders/"),
    NavItem("customers", "Customers", "people", "/customers/"),
    NavItem("products", "Products", "hanger", "/products/"),
    NavItem("production", "Production", "spool", "/production/"),
)
EMPLOYEE_NAV = (
    NavItem("my_work", "My work", "stopwatch", "/my-work/"),
    NavItem("my_pay", "My pay", "wallet", "/my-pay/"),
)
NAVS = {"owner": OWNER_NAV, "employee": EMPLOYEE_NAV}


def nav_items(role: str, active: str | None = None) -> list[dict]:
    """Items for the bottom nav of a role; `current` marks the active tab."""
    return [{"item": item, "current": item.key == active} for item in NAVS[role]]
