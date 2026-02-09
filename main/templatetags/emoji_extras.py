from django import template
from main.emoji import render_emoji_html, get_emoji_catalog

register = template.Library()


@register.filter
def emoji_codes(value):
    return render_emoji_html(value)


@register.simple_tag
def emoji_catalog():
    return get_emoji_catalog()
