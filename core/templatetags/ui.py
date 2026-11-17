from django import template

from core.forms_ui import choice_options, describedby, error_summary_text
from core.nav import nav_items
from core.thumbs import thumb_context

register = template.Library()


@register.inclusion_tag("components/nav.html")
def bottom_nav(role, active=None):
    return {"items": nav_items(role, active)}


@register.inclusion_tag("components/field.html")
def field(bound):
    hint = bool(bound.help_text)
    error = bool(bound.errors)
    attrs = {"class": "field__input"}
    ids = describedby(bound.auto_id, hint=hint, error=error)
    if ids:
        attrs["aria-describedby"] = ids
    if error:
        attrs["aria-invalid"] = "true"
    return {"f": bound, "input": bound.as_widget(attrs=attrs), "error": error}


@register.inclusion_tag("components/error_summary.html")
def error_summary(form, action):
    count = len(form.errors)
    return {
        "text": error_summary_text(count, action) if count else "",
        "non_field": form.non_field_errors(),
    }


@register.inclusion_tag("components/segmented.html")
def segmented(bound):
    return _choice_context(bound)


@register.inclusion_tag("components/radio_rows.html")
def radio_rows(bound, notes=None):
    return _choice_context(bound, notes)


@register.inclusion_tag("components/switch.html")
def switch(bound):
    return {
        "f": bound,
        "input": _toggle_input(bound, "switch", role="switch"),
        "error": bool(bound.errors),
    }


@register.inclusion_tag("components/checkbox_row.html")
def checkbox_row(bound):
    return {
        "f": bound,
        "input": _toggle_input(bound, "check"),
        "error": bool(bound.errors),
        "disabled": bound.field.disabled,
    }


@register.inclusion_tag("components/filter_chips.html")
def filter_chips(chips, label):
    return {"chips": chips, "label": label}


@register.inclusion_tag("components/thumb.html")
def thumb(name, src=None, count=0, size="sm"):
    return thumb_context(name, src, count, size)


def _choice_context(bound, notes=None):
    error = bool(bound.errors)
    options = choice_options(bound, notes)
    for o in options:
        ids = describedby(bound.auto_id, hint=False, error=error)
        if o["note"]:
            ids = f"{ids} {o['id']}_note".strip()
        o["describedby"] = ids
    return {"f": bound, "options": options, "error": error}


def _toggle_input(bound, css_class, **extra):
    attrs = {"class": css_class, **extra}
    error = bool(bound.errors)
    ids = describedby(bound.auto_id, hint=bool(bound.help_text), error=error)
    if ids:
        attrs["aria-describedby"] = ids
    if error:
        attrs["aria-invalid"] = "true"
    return bound.as_widget(attrs=attrs)
