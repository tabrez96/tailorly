from django import template

from production.timing import timer_text

register = template.Library()

register.filter("timer", timer_text)
