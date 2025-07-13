from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def dict_get(d, key):
    if not isinstance(d, dict):
        return ''
    return d.get(key, 0)
