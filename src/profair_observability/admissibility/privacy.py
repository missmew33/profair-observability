from __future__ import annotations

import os
from collections.abc import Iterable

DIRECT_IDENTIFIER_COLUMNS = {"full_name", "email", "phone", "telephone", "address", "postal_address"}


def restricted_mode_enabled() -> bool:
    return os.getenv("PROFAIR_RESTRICTED_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}


def direct_identifier_columns(columns: Iterable[str]) -> set[str]:
    return {c for c in columns if c.strip().lower() in DIRECT_IDENTIFIER_COLUMNS}


def enforce_public_mode(columns: Iterable[str]) -> None:
    found = direct_identifier_columns(columns)
    if found and not restricted_mode_enabled():
        raise ValueError("Public mode rejects direct identifiers. Set PROFAIR_RESTRICTED_MODE=1 only in an approved private/local environment. Detected: " + ", ".join(sorted(found)))
