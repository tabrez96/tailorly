from django import template

from staff.attendance import initials

register = template.Library()

register.filter("initials", initials)
