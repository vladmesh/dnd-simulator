"""Global test configuration — force English locale for deterministic assertions."""

import os

# Must be set before any dnd_simulator module is imported, because i18n.py
# reads DND_LANGUAGE at import time.
os.environ["DND_LANGUAGE"] = "en"
