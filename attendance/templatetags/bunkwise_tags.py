"""BunkWise custom template filters."""

from django import template

register = template.Library()


@register.filter
def index(lst, i):
    """Get list item by index: {{ my_list|index:0 }}"""
    try:
        return lst[int(i)]
    except (IndexError, TypeError, ValueError):
        return ''


@register.filter
def dict_key(d, key):
    """Get dict value by key: {{ my_dict|dict_key:key }}"""
    try:
        return d.get(int(key), [])
    except (TypeError, ValueError):
        return d.get(key, [])


@register.filter
def subtract(value, arg):
    """Subtract: {{ value|subtract:arg }}"""
    try:
        return float(value) - float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def mul(value, arg):
    """Multiply: {{ value|mul:arg }}"""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0


@register.filter
def pct_bar_width(value, max_val=100):
    """Clamp a percentage to 0–100 for CSS width."""
    try:
        return min(max(float(value), 0), 100)
    except (TypeError, ValueError):
        return 0


@register.filter
def risk_icon(risk):
    icons = {'SAFE': '✅', 'CAUTION': '⚠️', 'CRITICAL': '🚨'}
    return icons.get(risk, '❓')


@register.filter
def status_icon(status):
    icons = {
        'present':   '✅',
        'absent':    '❌',
        'cancelled': '🚫',
        'holiday':   '🏖️',
        'exam':      '📝',
        'event':     '🎉',
        'scheduled': '📅',
        'modified':  '🔄',
    }
    return icons.get(status, '❓')


@register.filter
def duration_fmt(minutes):
    """Convert minutes to human-readable format: 90 → '1h 30m'"""
    try:
        m = int(minutes)
        if m < 60:
            return f"{m}m"
        h, rem = divmod(m, 60)
        return f"{h}h {rem}m" if rem else f"{h}h"
    except (TypeError, ValueError):
        return str(minutes)


@register.simple_tag
def get_item(dictionary, key):
    """{% get_item my_dict key as val %}"""
    return dictionary.get(key)


@register.filter
def get_field(form, field_name):
    """Render a specific form field by name: {{ form|get_field:'my_field' }}"""
    try:
        return form[field_name]
    except KeyError:
        return ''


@register.filter
def split(value, arg):
    """Split a string by delimiter: {{ "a,b,c"|split:"," }}"""
    if isinstance(value, str):
        return value.split(arg)
    return []


