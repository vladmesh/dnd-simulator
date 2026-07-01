"""Domain exception types for the service layer.

Subclass ValueError so existing pytest.raises(ValueError, match=...) tests keep passing.
App-level handlers in adapters/api/app.py map these to HTTP status codes.
"""

from __future__ import annotations


class SessionNotFoundError(ValueError):
    pass


class PlayerNotFoundError(ValueError):
    pass


class InvalidLevelUpError(ValueError):
    pass
