from django import template
from dashboard.labels import word

register=template.Library()


@register.simple_tag(takes_context=True)
def bi(context,arabic,english):
    return word(context.get('lang','ar'),arabic,english)


@register.filter
def readable(value):
    if value is None or value=='':return '—'
    if isinstance(value,(list,tuple)):
        return ' · '.join(str(item) for item in value)
    return str(value)
