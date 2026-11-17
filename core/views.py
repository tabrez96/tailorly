from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static

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
    return render(request, "styleguide.html", {"theme": theme})
