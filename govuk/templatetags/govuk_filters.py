from django import template

register = template.Library()


@register.filter
def comma_number(value):
    if value in (None, ""):
        return "0"

    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return value
