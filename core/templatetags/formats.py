from django import template

from core.formats import (
    format_clock,
    format_day,
    format_duration,
    format_full_date,
    format_month,
    format_phone,
)
from core.money import format_inr

register = template.Library()

register.filter("inr", format_inr)
register.filter("day", format_day)
register.filter("clock", format_clock)
register.filter("duration", format_duration)
register.filter("phone", format_phone)
register.filter("month", format_month)
register.filter("fulldate", format_full_date)
