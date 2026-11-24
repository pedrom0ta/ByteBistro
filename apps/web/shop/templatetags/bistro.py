from django import template
from shop.storefront import photo

register = template.Library()
register.filter("photo", photo)

@register.filter
def brl(cents):
    return f"R$ {int(cents) // 100},{int(cents) % 100:02d}"
