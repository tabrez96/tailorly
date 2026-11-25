import json

from django import forms
from django.conf import settings
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import owner_required
from assistants import keys, prefs
from assistants.models import AccessKey, AssistantActivity
from core.pages import render_page
from reports.models import ShopSettings


class KeyNameForm(forms.Form):
    name = forms.CharField(
        max_length=40, label="Name", help_text="For example, Claude on tablet"
    )


def _redirect_303(path):
    response = HttpResponseRedirect(path)
    response.status_code = 303
    return response


def _context(request) -> dict:
    s = ShopSettings.current()
    active = list(AccessKey.active())
    return {
        "s": s,
        "address": settings.MCP_SERVER_URL or request.build_absolute_uri("/mcp"),
        "server_line": prefs.server_line(s.mcp_on, len(active)),
        "key_rows": [
            {"key": k, "used": prefs.key_used(k.last_used_at)} for k in active
        ],
        "activity": AssistantActivity.objects.select_related("key")[:20],
        "modes": [
            {
                "value": "read",
                "label": "Only read",
                "id": "mcp-mode-read",
                "checked": not s.mcp_can_change,
            },
            {
                "value": "change",
                "label": "Read and change",
                "id": "mcp-mode-change",
                "checked": s.mcp_can_change,
            },
        ],
    }


@owner_required
@require_GET
def assistants(request):
    return render_page(
        request,
        "assistants/assistants.html",
        {
            **_context(request),
            "title": "AI assistants",
            "overline": "Settings",
            "subpage": True,
            "back_url": reverse("settings"),
        },
    )


@owner_required
@require_POST
def assistants_set(request):
    parsed = prefs.parse(request.POST.get("name", ""), request.POST.get("value"))
    if parsed is None:
        response = HttpResponse(status=400)
        response["HX-Reswap"] = "none"
        return response
    field, value = parsed
    # Write only this field so a stale read can't undo another setting.
    ShopSettings.objects.update_or_create(pk=1, defaults={field: value})
    if not request.headers.get("HX-Request"):
        return _redirect_303(reverse("assistants"))
    return render(request, "assistants/_assistants.html", _context(request))


@owner_required
def assistant_key_new(request):
    form = KeyNameForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # The full key lives only in this one response: never log it or put it in
        # a toast, header, message or the session.
        raw, prefix, digest = keys.generate()
        key = AccessKey.objects.create(
            name=form.cleaned_data["name"], prefix=prefix, key_hash=digest
        )
        return render(
            request,
            "assistants/new_key_sheet.html",
            {"raw": raw, "key": key, **_context(request), "oob": True},
        )
    return render(
        request,
        "assistants/key_name_sheet.html",
        {"form": form, "action": request.get_full_path()},
        status=422 if request.method == "POST" else 200,
    )


@owner_required
@require_POST
def assistant_key_revoke(request, pk):
    key = get_object_or_404(AccessKey, pk=pk)
    AccessKey.objects.filter(pk=pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    response = render(request, "assistants/_assistants.html", _context(request))
    response["HX-Trigger"] = json.dumps({"toast": {"message": f"{key.name} revoked"}})
    return response
