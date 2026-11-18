from django import template

from staff.attendance import first_name, initials

register = template.Library()

register.filter("initials", initials)
register.filter("first_name", first_name)
