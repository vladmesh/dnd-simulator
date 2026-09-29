"""The gettext catalogs must stay in sync with the code.

Extracts every ``_()`` / ``ngettext()`` / ``N_()`` msgid from ``src/dnd_simulator`` with the same babel mapping
``make messages`` uses, then checks that the committed ``messages.pot`` lists exactly those msgids, that the ru
``.po`` translates each of them, and that the committed ``.mo`` is the compilation of the ``.po``.

Fix a failure with ``make messages`` (template), a ru translation in the ``.po``, then ``make compile-messages``.
"""

from __future__ import annotations

import gettext
from io import BytesIO
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.extract import DEFAULT_KEYWORDS, extract_from_dir
from babel.messages.frontend import parse_mapping_cfg
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src" / "dnd_simulator"
_LOCALE = _SRC / "locale"
_POT = _LOCALE / "messages.pot"
_RU_PO = _LOCALE / "ru" / "LC_MESSAGES" / "dnd_simulator.po"
_RU_MO = _LOCALE / "ru" / "LC_MESSAGES" / "dnd_simulator.mo"

MsgId = str | tuple[str, ...]


def _code_msgids() -> dict[MsgId, str]:
    """Every msgid the extractor finds in the code, mapped to its first source location."""
    with (_ROOT / "babel.cfg").open() as cfg:
        method_map, options_map = parse_mapping_cfg(cfg)
    found: dict[MsgId, str] = {}
    for filename, lineno, message, _comments, _context in extract_from_dir(
        str(_SRC), method_map, options_map, keywords=DEFAULT_KEYWORDS
    ):
        msgid: MsgId = message if isinstance(message, str) else tuple(m for m in message if m is not None)
        if msgid:
            found.setdefault(msgid, f"{filename}:{lineno}")
    return found


def _read_catalog(path: Path) -> Catalog:
    with path.open("rb") as handle:
        return read_po(handle)


def _catalog_msgids(catalog: Catalog) -> set[MsgId]:
    return {message.id if isinstance(message.id, str) else tuple(message.id) for message in catalog if message.id}


def test_pot_lists_exactly_the_code_msgids() -> None:
    code = set(_code_msgids())
    pot = _catalog_msgids(_read_catalog(_POT))
    missing = sorted(map(str, code - pot))
    stale = sorted(map(str, pot - code))
    assert not missing and not stale, f"messages.pot is out of date, run `make messages`: {missing=} {stale=}"


def test_every_code_msgid_has_a_ru_translation() -> None:
    po = _read_catalog(_RU_PO)
    untranslated: list[str] = []
    for msgid, location in _code_msgids().items():
        key = msgid if isinstance(msgid, str) else msgid[0]
        message = po.get(key)
        if message is None or message.fuzzy:
            untranslated.append(f"{location}: {msgid!r}")
            continue
        if isinstance(msgid, str):
            translated = isinstance(message.string, str) and bool(message.string)
        else:
            forms = message.string if isinstance(message.string, tuple) else ()
            translated = tuple(message.id) == msgid and len(forms) == po.num_plurals and all(forms)
        if not translated:
            untranslated.append(f"{location}: {msgid!r}")
    assert not untranslated, "Missing ru translations:\n" + "\n".join(untranslated)


def test_ru_po_has_no_duplicate_msgids() -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    current: list[str] | None = None
    for line in [*_RU_PO.read_text(encoding="utf-8").splitlines(), ""]:
        if line.startswith("msgid "):
            current = [line[len("msgid ") :]]
        elif current is not None and line.startswith('"'):
            current.append(line)
        elif current is not None:
            msgid = "".join(current)
            if msgid in seen:
                duplicates.append(msgid)
            seen.add(msgid)
            current = None
    assert not duplicates, f"Duplicate msgids in the ru .po: {duplicates}"


def test_ru_mo_is_compiled_from_the_po() -> None:
    compiled = BytesIO()
    write_mo(compiled, _read_catalog(_RU_PO))
    compiled.seek(0)
    expected = gettext.GNUTranslations(compiled)
    with _RU_MO.open("rb") as handle:
        committed = gettext.GNUTranslations(handle)
    assert committed._catalog == expected._catalog, "ru .mo is stale, run `make compile-messages`"  # type: ignore[attr-defined]


def test_every_action_description_localizes_in_ru() -> None:
    from dnd_simulator.core.action import ActionType
    from dnd_simulator.core.action_defs import get_action_def
    from dnd_simulator.i18n import _, language_context

    english: list[str] = []
    with language_context("ru"):
        for action_type in ActionType:
            definition = get_action_def(action_type)
            for text in (definition.description, *(param.description for param in definition.params)):
                if not any("Ѐ" <= ch <= "ӿ" for ch in _(text)):
                    english.append(f"{action_type}: {text!r}")
    assert not english, "Action texts shown untranslated in ru:\n" + "\n".join(english)
