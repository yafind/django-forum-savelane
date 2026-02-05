import os
import re
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import escape
from django.utils.safestring import mark_safe

EMOJI_MAP = {
    'smile_okay': '😊',
    'thumbs_up': '👍',
    'heart': '❤️',
    'fire': '🔥',
    'clap': '👏',
    'party': '🥳',
    'wink': '😉',
    'sad': '😢',
}

EMOJI_EXTS = ['gif', 'png', 'webp']
CODE_PATTERN = re.compile(r':([a-z0-9_+-]{2,}):')


def _find_emoji_file(code):
    media_root = getattr(settings, 'MEDIA_ROOT', '') or ''
    static_root = os.path.join(settings.BASE_DIR, 'main', 'static')
    collected_static_root = getattr(settings, 'STATIC_ROOT', '') or ''

    for ext in EMOJI_EXTS:
        filename = f'{code}.{ext}'
        if media_root:
            media_path = os.path.join(media_root, 'emoji', filename)
            if os.path.exists(media_path):
                return f'{settings.MEDIA_URL.rstrip("/")}/emoji/{filename}'
        if collected_static_root:
            collected_path = os.path.join(collected_static_root, 'emoji', filename)
            if os.path.exists(collected_path):
                return f'{settings.STATIC_URL.rstrip("/")}/emoji/{filename}'
        static_path = os.path.join(static_root, 'emoji', filename)
        if os.path.exists(static_path):
            return static(f'emoji/{filename}')

    return ''


def _list_codes_from_dir(path):
    if not path or not os.path.isdir(path):
        return []
    codes = []
    for name in os.listdir(path):
        base, ext = os.path.splitext(name)
        ext = ext.lstrip('.').lower()
        if base and ext in EMOJI_EXTS:
            codes.append(base)
    return codes


def get_emoji_catalog():
    media_root = getattr(settings, 'MEDIA_ROOT', '') or ''
    static_root = os.path.join(settings.BASE_DIR, 'main', 'static')
    collected_static_root = getattr(settings, 'STATIC_ROOT', '') or ''

    code_set = set(EMOJI_MAP.keys())
    code_set.update(_list_codes_from_dir(os.path.join(media_root, 'emoji')))
    code_set.update(_list_codes_from_dir(os.path.join(static_root, 'emoji')))
    code_set.update(_list_codes_from_dir(os.path.join(collected_static_root, 'emoji')))

    catalog = []
    for code in sorted(code_set):
        catalog.append({
            'code': code,
            'char': EMOJI_MAP.get(code, ''),
            'url': _find_emoji_file(code)
        })
    return catalog


def render_emoji_html(value):
    if value is None:
        return ''

    text = escape(str(value))

    def replacer(match):
        code = match.group(1)
        emoji_url = _find_emoji_file(code)
        if emoji_url:
            return (
                f'<img src="{emoji_url}" alt=":{code}:" '
                'class="emoji" width="20" height="20" loading="lazy">'
            )
        if code in EMOJI_MAP:
            return EMOJI_MAP[code]
        return match.group(0)

    text = CODE_PATTERN.sub(replacer, text)
    text = text.replace('\n', '<br>')
    return mark_safe(text)
