from django import template

from core.formats import format_clock, format_day, format_duration
from core.money import format_inr

register = template.Library()

register.filter("inr", format_inr)
register.filter("day", format_day)
register.filter("clock", format_clock)
register.filter("duration", format_duration)
