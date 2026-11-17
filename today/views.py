from accounts.decorators import owner_required
from core.pages import render_page


@owner_required
def today(request):
    return render_page(request, "today/today.html", {"title": "Today", "tab": "today"})
