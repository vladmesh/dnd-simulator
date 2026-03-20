"""Internationalization setup — gettext with English base, translated .po files."""

import gettext
import os
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent / "locale"
_lang = os.getenv("DND_LANGUAGE", "ru")
_translation = gettext.translation(
    "dnd_simulator",
    localedir=str(_LOCALE_DIR),
    languages=[_lang],
    fallback=True,
)
_ = _translation.gettext
