import json

from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.utils.cache import patch_vary_headers

from accounts.roles import role_for
from core import assets


def is_partial(headers) -> bool:
    return headers.get("HX-Request-Type") == "partial"


def render_page(
    request: HttpRequest, template: str, context: dict, *, status: int = 200
) -> HttpResponse:
    """Render a page: the fragment for htmx partial requests, else the full shell.

    `context` needs `title` (the h1 text); `tab` (nav key) and `back_url` are optional.
    """
    ctx = {
        **context,
        "page_template": template,
        "role": role_for(request.user),
        "tab": context.get("tab"),
        "doc_title": f"{context['title']} · Tailorly",
    }
    if is_partial(request.headers):
        response = render(
            request, "shell/page.html", ctx | {"partial": True}, status=status
        )
    else:
        hx_headers = json.dumps(
            {
                "X-CSRFToken": get_token(request),
                "X-Asset-Version": assets.asset_version(),
            }
        )
        response = render(
            request,
            "shell/shell.html",
            ctx | {"partial": False, "hx_headers": hx_headers},
            status=status,
        )
    patch_vary_headers(response, ["HX-Request-Type"])
    return response


def sheet_saved(response: HttpResponse, toast: str) -> HttpResponse:
    """Close the open sheet and show a toast, via the HX-Trigger header.

    The swap is skipped so the form stays put and the event bubbles to the window.
    """
    response["HX-Reswap"] = "none"
    response["HX-Trigger"] = json.dumps(
        {"sheet:close": True, "toast": {"message": toast}}
    )
    return response
