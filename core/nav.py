from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str
    href: str
    hold: str = ""  # where a 500 ms press on the tab goes


OWNER_NAV = (
    NavItem("today", "Today", "house", "/"),
    NavItem("orders", "Orders", "list", "/orders/", "/orders/new/"),
    NavItem("customers", "Customers", "people", "/customers/", "/customers/?add=1"),
    NavItem("products", "Products", "hanger", "/products/", "/products/?add=1"),
    NavItem(
        "production",
        "Production",
        "spool",
        "/production/",
        "/production/plan/?assign=next",
    ),
)
EMPLOYEE_NAV = (
    NavItem("my_work", "My work", "stopwatch", "/my-work/"),
    NavItem("my_pay", "My pay", "wallet", "/my-pay/"),
)
NAVS = {"owner": OWNER_NAV, "employee": EMPLOYEE_NAV}


def nav_items(role: str, active: str | None = None) -> list[dict]:
    """Items for the bottom nav of a role; `current` marks the active tab."""
    return [{"item": item, "current": item.key == active} for item in NAVS[role]]
