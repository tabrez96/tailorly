from django import template

from core.nav import nav_items

register = template.Library()


@register.inclusion_tag("components/nav.html")
def bottom_nav(role, active=None):
    return {"items": nav_items(role, active)}
