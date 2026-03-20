"""Internationalization setup — gettext with per-session language via contextvars."""

import gettext
import os
from contextvars import ContextVar
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locale"
_default_lang = os.getenv("DND_LANGUAGE", "ru")

# Pre-load translations for known languages
_translations: dict[str, gettext.GNUTranslations | gettext.NullTranslations] = {}


def _get_translation(lang: str) -> gettext.GNUTranslations | gettext.NullTranslations:
    if lang not in _translations:
        _translations[lang] = gettext.translation(
            "dnd_simulator",
            localedir=str(_LOCALE_DIR),
            languages=[lang],
            fallback=True,
        )
    return _translations[lang]


# Context var for per-request/per-session language
current_lang: ContextVar[str] = ContextVar("current_lang", default=_default_lang)


def _(message: str) -> str:
    """Translate a string using the current context language."""
    lang = current_lang.get()
    return _get_translation(lang).gettext(message)


def set_language(lang: str) -> None:
    """Set the language for the current context (thread/coroutine)."""
    current_lang.set(lang)
