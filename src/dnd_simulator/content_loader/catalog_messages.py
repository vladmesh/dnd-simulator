"""Translatable strings of the YAML catalogs — item names and attack names.

These names are content, not code, so ``pygettext3`` never sees them, yet the player sees them
through gettext (combat log, combat panel, inventory). This module is the one list of them:
``make messages`` appends them to the .pot, and a unit test requires a Russian translation for
each, so a new catalog entry cannot ship untranslated.

Monster *names* are not here: they are ``LocalizedText`` maps in the YAML itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.schemas import ItemContent, MonsterTemplateContent


def catalog_msgids(content_root: Path) -> dict[str, list[str]]:
    """Every translatable catalog string mapped to the catalog files that use it.

    Covers item ``name`` and weapon ``attack_name`` (``catalogs/items``) and monster attack
    ``name`` (``catalogs/monsters``). References are ``catalogs/<dir>/<id>.yaml`` paths.
    """
    msgids: dict[str, list[str]] = {}

    def add(msgid: str, ref: str) -> None:
        if msgid:
            msgids.setdefault(msgid, []).append(ref)

    catalogs = content_root / "catalogs"
    for item_id, item in load_catalog(catalogs / "items", ItemContent).items():
        ref = f"catalogs/items/{item_id}.yaml"
        add(item.name, ref)
        add(item.attack_name or "", ref)
    for monster_id, monster in load_catalog(catalogs / "monsters", MonsterTemplateContent).items():
        for attack in monster.attacks:
            add(attack.name, f"catalogs/monsters/{monster_id}.yaml")
    return msgids


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def pot_entries(msgids: dict[str, list[str]], existing: set[str]) -> str:
    """.pot entries for the msgids not in *existing*, sorted, with ``#:`` source references."""
    entries = []
    for msgid in sorted(set(msgids) - existing):
        refs = " ".join(f"content/{ref}" for ref in sorted(set(msgids[msgid])))
        entries.append(f'#: {refs}\nmsgid {_quote(msgid)}\nmsgstr ""\n')
    return "\n".join(entries)


def append_to_pot(pot_path: Path, content_root: Path) -> int:
    """Append the catalog msgids missing from *pot_path*; return how many were added."""
    from babel.messages.pofile import read_po

    text = pot_path.read_text(encoding="utf-8")
    with pot_path.open("rb") as fh:
        existing = {str(message.id) for message in read_po(fh) if message.id}
    missing = pot_entries(catalog_msgids(content_root), existing)
    if missing:
        pot_path.write_text(text.rstrip("\n") + "\n\n" + missing, encoding="utf-8")
    return missing.count("\nmsgid ")


if __name__ == "__main__":  # pragma: no cover — invoked by ``make messages``
    added = append_to_pot(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"catalog msgids appended: {added}")
