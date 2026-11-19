from accounts.roles import OWNER, role_for
from orders.models import Rework
from staff.models import Employee


def can_see_order(user, order) -> bool:
    """Owner: every order. Employee: orders (or reworks) assigned to them."""
    if not user.is_authenticated:
        return False
    if role_for(user) == OWNER:
        return True
    try:
        employee = user.employee
    except Employee.DoesNotExist:
        return False
    return (
        order.assignee_id == employee.id
        or Rework.objects.filter(item__order=order, assignee=employee).exists()
    )
