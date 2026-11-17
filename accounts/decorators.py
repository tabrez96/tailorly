from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from accounts.roles import EMPLOYEE, OWNER, home_url, role_for


def role_required(role: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            actual = role_for(request.user)
            if actual != role:
                return redirect(home_url(actual))
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


owner_required = role_required(OWNER)
employee_required = role_required(EMPLOYEE)
