from django.utils import timezone

from accounts.decorators import employee_required
from core.formats import format_day
from core.pages import render_page
from staff.attendance import day_card


@employee_required
def my_work(request):
    now = timezone.now()
    return render_page(
        request,
        "production/my_work.html",
        {
            "title": "My work",
            "tab": "my_work",
            "overline": format_day(now).upper(),
            "day": day_card(getattr(request.user, "employee", None), now),
        },
    )
