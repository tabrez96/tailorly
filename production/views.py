from accounts.decorators import employee_required
from core.pages import render_page


@employee_required
def my_work(request):
    return render_page(
        request, "production/my_work.html", {"title": "My work", "tab": "my_work"}
    )
