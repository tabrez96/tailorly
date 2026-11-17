OWNER, EMPLOYEE = "owner", "employee"


def role_for(user) -> str:
    """The owner is whoever is in the "owner" group; everyone else is an employee."""
    if user.is_authenticated and user.groups.filter(name=OWNER).exists():
        return OWNER
    return EMPLOYEE


def home_url(role: str) -> str:
    return "/" if role == OWNER else "/my-work/"
