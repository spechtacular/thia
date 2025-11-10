from django import template

register = template.Library()

@register.filter
def replace_apostrophe(value):
    return value.replace("'", "_") if isinstance(value, str) else value

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})
