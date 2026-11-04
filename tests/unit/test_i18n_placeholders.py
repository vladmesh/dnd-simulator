"""Check ru translation formatting, not catalog completeness or .mo synchronization."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from string import Formatter

import pytest
from babel.messages.catalog import Message
from babel.messages.pofile import read_po

_RU_PO = Path(__file__).resolve().parents[2] / "src/dnd_simulator/locale/ru/LC_MESSAGES/dnd_simulator.po"
_FORMATTER = Formatter()
_PRINTF = re.compile(
    r"%(?:%|(?:\((?P<name>[^)]+)\))?[-+#0 ]*(?P<width>\d+|\*)?"
    r"(?:\.(?P<precision>\d+|\*))?[hlL]?(?P<kind>[diouxXeEfFgGcrsa]))"
)
BraceField = tuple[str, str, str | None]


def _brace_fields(text: str) -> list[BraceField]:
    """Preserve names, conversions, specs and multiplicity; parse ignores {{ and }}."""
    fields: list[BraceField] = []
    for _literal, name, spec, conversion in _FORMATTER.parse(text):
        if name is not None:
            fields.append((name, spec, conversion))
            fields.extend(_brace_fields(spec))
    return fields


def _printf_fields(text: str) -> list[re.Match[str]]:
    return [match for match in _PRINTF.finditer(text) if match.group() != "%%"]


def _brace_arguments(source: str) -> tuple[list[object], dict[str, object]]:
    """Choose real Python values from source specs, never from translated field names."""
    specs: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    automatic = 0
    for name, spec, conversion in _brace_fields(source):
        if name == "":
            name = str(automatic)
            automatic += 1
        specs[name].append((spec, conversion))
    args: list[object] = [1] * (1 + max((int(name) for name in specs if name.isdecimal()), default=-1))
    kwargs: dict[str, object] = {name: 1 for name in specs if not name.isdecimal()}
    for name, formats in specs.items():
        for value in (1, "x", 1.0):
            try:
                for spec, conversion in formats:
                    converted = _FORMATTER.convert_field(value, conversion) if conversion else value
                    _FORMATTER.format_field(converted, spec.format(*args, **kwargs))
            except (ValueError, TypeError):
                continue
            if name.isdecimal():
                args[int(name)] = value
            else:
                kwargs[name] = value
            break
        else:
            raise ValueError(f"Cannot build a dummy for source field {name!r}: {formats!r}")
    source.format(*args, **kwargs)  # Ensure a bad dummy is not mistaken for a translation defect.
    return args, kwargs


def _printf_arguments(source: str) -> tuple[object, ...] | dict[str, object]:
    fields = _printf_fields(source)
    if any(field.group("name") is not None for field in fields):
        values: dict[str, object] = {}
        for field in fields:
            name = field.group("name")
            # Integers also work for %s/%r, including a name reused with %d.
            values[name] = 1
        source % values
        return values
    positional: list[object] = []
    for field in fields:
        for part in ("width", "precision"):
            if field.group(part) == "*":
                positional.append(1)
        positional.append("x" if field.group("kind") in "sra" else 1)
    result = tuple(positional)
    source % result
    return result


def _layout(text: str) -> tuple[int, int, int]:
    """Compare edge spaces and terminal newlines, not translated internal whitespace."""
    without_newlines = text.rstrip("\n")
    return (
        len(text) - len(text.lstrip(" ")),
        len(without_newlines) - len(without_newlines.rstrip(" ")),
        len(text) - len(without_newlines),
    )


def _translation_offenders(source: str, translation: str) -> list[str]:
    offenders: list[str] = []
    try:
        expected_braces = Counter(_brace_fields(source))
        actual_braces = Counter(_brace_fields(translation))
        if actual_braces != expected_braces:
            offenders.append(f"brace fields: expected {expected_braces!r}, got {actual_braces!r}")
    except ValueError as exc:
        offenders.append(f"invalid brace syntax: {exc}")
    expected_printf = Counter(field.group() for field in _printf_fields(source))
    actual_printf = Counter(field.group() for field in _printf_fields(translation))
    if actual_printf != expected_printf:
        offenders.append(f"printf fields: expected {expected_printf!r}, got {actual_printf!r}")
    try:
        args, kwargs = _brace_arguments(source)
        translation.format(*args, **kwargs)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError) as exc:
        offenders.append(f".format() failed: {type(exc).__name__}: {exc}")
    if expected_printf:
        try:
            translation % _printf_arguments(source)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
            offenders.append(f"% formatting failed: {type(exc).__name__}: {exc}")
    if _layout(source) != _layout(translation):
        offenders.append(f"edge spaces / trailing newlines: expected {_layout(source)}, got {_layout(translation)}")
    return offenders


def _message_offenders(message: Message) -> list[str]:
    if not message.id:  # The gettext metadata header is not a translated UI message.
        return []
    sources = (message.id,) if isinstance(message.id, str) else message.id
    translations = (message.string,) if isinstance(message.string, str) else (message.string or ())
    offenders: list[str] = []
    if message.fuzzy and any(translations):
        offenders.append(f"{sources[0]!r}: fuzzy entry has a translation")
    for index, translation in enumerate(translations):
        if not translation:  # Missing translations are covered by test_i18n_catalog.py.
            continue
        # Compare form 0 with msgid, and forms 1 and 2 with msgid_plural.
        source = sources[0] if index == 0 else sources[-1]
        offenders.extend(
            f"{sources[0]!r}, msgstr[{index}]: {problem}" for problem in _translation_offenders(source, translation)
        )
    return offenders


def test_ru_translation_format_safety() -> None:
    with _RU_PO.open("rb") as handle:
        catalog = read_po(handle)
    offenders: list[str] = []
    for message in catalog:
        offenders.extend(_message_offenders(message))
    assert offenders == [], "\n".join(offenders)


@pytest.mark.parametrize(
    ("source", "translation"),
    [
        ("{name!r}: {value:08.2f}", "{value:08.2f}: {name!r}"),
        ("{} {} {number:d}", "{number:d} {} {}"),
        ("{0:s} {1:.2f}", "{1:.2f} {0:s}"),
        ("{value:{width}.{precision}f}", "{value:{width}.{precision}f}"),
        ("{{literal}} {name} {{}}", "{{other literal}} {name} {{}}"),
        ("%s %d %%", "%s %d %%"),
        ("%(name)s %(count)03d", "%(count)03d %(name)s"),
        ("%*.*f", "%*.*f"),
        ("  {name}\n\n", "  {name}\n\n"),
    ],
)
def test_safe_format_examples(source: str, translation: str) -> None:
    offenders = _translation_offenders(source, translation)
    assert offenders == [], "\n".join(offenders)


@pytest.mark.parametrize(
    ("source", "translation", "problem"),
    [
        ("{name}", "{other}", "brace fields"),
        ("{name} {name}", "{name}", "brace fields"),
        ("{} {}", "{}", "brace fields"),
        ("{name!r}", "{name}", "brace fields"),
        ("{value:.2f}", "{value:.3f}", "brace fields"),
        ("{name}", "{name", "invalid brace syntax"),
        ("{:s} {:d}", "{:d} {:s}", ".format() failed"),
        ("%s %s", "%s", "printf fields"),
        ("%(name)s", "%(name)d", "printf fields"),
        ("%(name)s", "%(other)s", "% formatting failed"),
        ("%s %d", "%d %s", "% formatting failed"),
        ("%d", "%d %", "% formatting failed"),
        ("  text", " text", "edge spaces"),
        ("text ", "text", "edge spaces"),
        ("text\n\n", "text\n", "trailing newlines"),
    ],
)
def test_unsafe_format_examples(source: str, translation: str, problem: str) -> None:
    offenders: list[str] = []
    if not any(problem in offender for offender in _translation_offenders(source, translation)):
        offenders.append(f"Did not detect {problem}")
    assert offenders == [], "\n".join(offenders)


def test_plural_and_fuzzy_examples() -> None:
    safe = Message(("{one} item", "{many} items"), ("{one} item", "{many} items", "{many} items"))
    bad_plural = Message(safe.id, ("{one} item", "{wrong} items", "{wrong} items"))
    fuzzy = Message("text", "translation", flags={"fuzzy"})
    untranslated_fuzzy = Message("text", "", flags={"fuzzy"})
    offenders = _message_offenders(safe) + _message_offenders(untranslated_fuzzy)
    plural_problems = _message_offenders(bad_plural)
    for index in (1, 2):
        if not any(f"msgstr[{index}]" in problem for problem in plural_problems):
            offenders.append(f"Did not detect unsafe plural form {index}")
    if not _message_offenders(fuzzy):
        offenders.append("Did not detect fuzzy translation")
    assert offenders == [], "\n".join(offenders)
