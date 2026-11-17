from django import forms
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static

from accounts.decorators import owner_required
from core import styleguide as sg
from core.pages import render_page, sheet_saved

THEME_COLOUR = "#8A2E62"  # --pri, light; manifests can't read CSS tokens
BACKGROUND_COLOUR = "#F6F2ED"  # --bg, light


def manifest(request: HttpRequest) -> JsonResponse:
    icons = [
        {"src": static("brand/icon-192.png"), "sizes": "192x192", "type": "image/png"},
        {"src": static("brand/icon-512.png"), "sizes": "512x512", "type": "image/png"},
        {"src": static("brand/mark.svg"), "sizes": "any", "type": "image/svg+xml"},
    ]
    data = {
        "name": "Tailorly",
        "short_name": "Tailorly",
        "start_url": "/",
        "display": "standalone",
        "background_color": BACKGROUND_COLOUR,
        "theme_color": THEME_COLOUR,
        "icons": icons,
    }
    return JsonResponse(data, content_type="application/manifest+json")


def styleguide(request: HttpRequest) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404
    theme = "dark" if request.GET.get("theme") == "dark" else None
    context = {"theme": theme, **sg.context(request.GET.get("status"))}
    return render(request, "styleguide.html", context)


class SampleForm(forms.Form):
    name = forms.CharField(max_length=40)
    note = forms.CharField(required=False)


@owner_required
def shell_check(request: HttpRequest) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404
    context = {"title": "Shell check", "back_url": "/"}
    return render_page(request, "core/shell_check.html", context)


@owner_required
def sample_sheet(request: HttpRequest) -> HttpResponse:
    if not settings.DEBUG:
        raise Http404
    form = SampleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return sheet_saved(HttpResponse(""), "Saved")
    status = 422 if request.method == "POST" else 200
    return render(request, "core/sample_sheet.html", {"form": form}, status=status)
