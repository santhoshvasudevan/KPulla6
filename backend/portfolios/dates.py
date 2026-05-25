from __future__ import annotations

from datetime import date


def current_date() -> date:
    """Return today's date (patchable in tests)."""
    return date.today()
