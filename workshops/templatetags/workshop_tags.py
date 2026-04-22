import os
from django import template

register = template.Library()

@register.filter
def basename(value):
    return os.path.basename(value)

@register.simple_tag
def set_var(val=None):
    return val
