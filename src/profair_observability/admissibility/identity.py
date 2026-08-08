from __future__ import annotations

import re
from dataclasses import dataclass

from unidecode import unidecode

from .schema import IdentityStatus
from .search import name_variants


def _norm(text: str) -> str:
    text = unidecode(text or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _org_terms(org: str) -> list[str]:
    stop = {"the", "and", "of", "de", "del", "la", "las", "los", "el", "da", "do", "di", "spa", "sl", "sa", "srl", "ltd", "limited", "inc", "group", "company", "corporation"}
    return [t for t in _norm(org).split() if len(t) >= 4 and t not in stop]


@dataclass(slots=True)
class IdentityMatch:
    status: str
    excerpt: str = ""
    reason: str = ""
    name_position: int | None = None


class IdentityResolver:
    def __init__(self, window_chars: int = 300) -> None:
        self.window_chars = window_chars

    def evaluate(self, full_text: str, full_name: str, org_target: str) -> IdentityMatch:
        if not full_text.strip():
            return IdentityMatch(IdentityStatus.REJECTED_NO_NAME.value, reason="No source text.")
        if not org_target.strip():
            return IdentityMatch(IdentityStatus.REJECTED_NO_CONTEXT.value, reason="No organisation context.")
        text_norm = _norm(full_text)
        org_tokens = _org_terms(org_target) or _norm(org_target).split()
        positions = []
        for variant in name_variants(full_name):
            vnorm = _norm(variant)
            start = 0
            while vnorm:
                pos = text_norm.find(vnorm, start)
                if pos < 0:
                    break
                positions.append(pos)
                start = pos + max(1, len(vnorm))
        if not positions:
            return IdentityMatch(IdentityStatus.REJECTED_NO_NAME.value, reason="No discriminating name variant found.")
        for pos in positions:
            start, end = max(0, pos - self.window_chars), min(len(text_norm), pos + self.window_chars)
            window = text_norm[start:end]
            org_norm = _norm(org_target)
            if org_norm and org_norm in window:
                return IdentityMatch(IdentityStatus.ACCEPTED.value, excerpt=window, reason="Name and full organisation context co-occur within identity window.", name_position=pos)
            matched = [term for term in org_tokens if term in window]
            if matched:
                return IdentityMatch(IdentityStatus.ACCEPTED_PROVISIONAL.value, excerpt=window, reason=f"Name co-occurs with organisation token(s): {', '.join(matched[:3])}.", name_position=pos)
        return IdentityMatch(IdentityStatus.REJECTED_NO_COOCCURRENCE.value, reason="Name found, but organisation context did not co-occur in the identity window.")
