from django import template

register = template.Library()

@register.filter
def replace_apostrophe(value):
    return value.replace("'", "_") if isinstance(value, str) else value
