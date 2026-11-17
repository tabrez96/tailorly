from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import resolve_url

from core import assets


def is_login_redirect(location: str) -> bool:
    return urlsplit(location).path == resolve_url(settings.LOGIN_URL)


class HtmxShellMiddleware:
    """Keeps the single-page shell honest for htmx requests.

    A stale asset version asks the browser to reload the shell; a redirect to
    sign-in (expired session) becomes a client-side redirect.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # History restores lose HX-Request but still need the sign-in redirect.
        htmx = (
            request.headers.get("HX-Request") == "true"
            or request.headers.get("HX-History-Restore-Request") == "true"
        )
        sent = request.headers.get("X-Asset-Version")
        if htmx and sent and sent != assets.asset_version():
            return HttpResponse(headers={"HX-Refresh": "true"})
        response = self.get_response(request)
        if (
            htmx
            and response.status_code == 302
            and is_login_redirect(response["Location"])
        ):
            return HttpResponse(headers={"HX-Redirect": response["Location"]})
        return response
