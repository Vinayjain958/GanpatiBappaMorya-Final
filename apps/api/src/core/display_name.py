"""Shared helper for deriving a safe display name from a User account.

Extracted from `services/reviews.py` so the traveler contribution feature
(which needs to show "Added by <name>" without leaking the account's raw
email) can reuse the exact same derivation instead of a second
copy — no `display_name` column exists on User/Traveler today
(`schemas/auth.py`'s registration field is accepted but never persisted).
"""

from __future__ import annotations

from src.models.user import User


def derive_display_name(user: User) -> str:
    local_part = user.email.split("@", 1)[0]
    cleaned = "".join(ch if ch.isalnum() else " " for ch in local_part).strip()
    if not cleaned:
        return "LocaLens traveler"
    return cleaned.title()[:80]
