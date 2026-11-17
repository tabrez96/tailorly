from accounts.decorators import employee_required
from core.pages import render_page


@employee_required
def my_pay(request):
    return render_page(
        request, "staff/my_pay.html", {"title": "My pay", "tab": "my_pay"}
    )
