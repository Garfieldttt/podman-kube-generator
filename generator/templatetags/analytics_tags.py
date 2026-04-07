from django import template

register = template.Library()


@register.filter
def country_flag(code):
    """Konvertiert 2-Buchstaben-Ländercode in Flaggen-Emoji (AT → 🇦🇹)"""
    if not code or len(code) != 2:
        return ''
    code = code.upper()
    return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))
