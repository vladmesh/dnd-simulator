## [audit] — 2026-07-16
- **Type**: bug
- **Quote**: "ls src/dnd_simulator/rules/*.py | sed 's|src/dnd_simulator/||;s|\.py||;s|/|_|g' | while read mod; do [ -f \"tests/unit/test_${mod}.py\" ] ..."
- **Problem**: The expected test filename `tests/unit/test_rules_<mod>.py` never matches this repo's convention (`tests/unit/test_<mod>.py`, e.g. `test_dice.py`), so the loop reports all 30 rules modules as MISSING on every run and the gap check has to be redone by hand.
- **Suggested fix**: Drop the `rules_` prefix from the expected name and treat a module as covered if any `tests/unit/test_*<mod>*.py` exists or any test file imports it.
