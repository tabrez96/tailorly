from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect

from accounts.roles import EMPLOYEE, OWNER, home_url, role_for


def _is_htmx(request) -> bool:
    return (
        request.headers.get("HX-Request") == "true"
        or request.headers.get("HX-History-Restore-Request") == "true"
    )


def role_required(role: str):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            actual = role_for(request.user)
            if actual != role:
                home = home_url(actual)
                if _is_htmx(request):
                    return HttpResponse(status=403, headers={"HX-Redirect": home})
                return redirect(home)
            return view(request, *args, **kwargs)

        wrapper.required_role = role
        return wrapper

    return decorator


owner_required = role_required(OWNER)
employee_required = role_required(EMPLOYEE)
