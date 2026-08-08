from __future__ import annotations

import re
from dataclasses import dataclass

from unidecode import unidecode

from .schema import IdentityStatus
from .search import name_variants

MAX_INSERTED_NAME_TOKENS = 5


def _norm(text: str) -> str:
    text = unidecode(text or "").casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _org_terms(org: str) -> list[str]:
    stop = {
        "the",
        "and",
        "of",
        "de",
        "del",
        "la",
        "las",
        "los",
        "el",
        "da",
        "do",
        "di",
        "spa",
        "sl",
        "sa",
        "srl",
        "ltd",
        "limited",
        "inc",
        "group",
        "company",
        "corporation",
    }
    return [t for t in _norm(org).split() if len(t) >= 4 and t not in stop]


def find_name_spans(text_norm: str, full_name: str) -> list[tuple[int, int, str]]:
    """Find exact and conservative expanded-name spans.

    Expanded matching handles records where the source contains additional legal or
    middle-name tokens while preserving every token from the recorded name in order.
    Such matches are always treated as provisional identity evidence.
    """
    spans: list[tuple[int, int, str]] = []
    seen: set[tuple[int, int]] = set()

    for variant in name_variants(full_name):
        target = _norm(variant)
        if not target:
            continue
        start = 0
        while True:
            pos = text_norm.find(target, start)
            if pos < 0:
                break
            span = (pos, pos + len(target))
            if span not in seen:
                seen.add(span)
                spans.append((span[0], span[1], "exact"))
            start = pos + max(1, len(target))

    canonical_tokens = _norm(full_name).split()
    if len(canonical_tokens) >= 3:
        pattern = rf"\b{re.escape(canonical_tokens[0])}"
        for token in canonical_tokens[1:]:
            pattern += rf"(?:\s+[a-z0-9]+){{0,3}}\s+{re.escape(token)}"
        pattern += r"\b"

        canonical = " ".join(canonical_tokens)
        for match in re.finditer(pattern, text_norm):
            matched = match.group(0)
            inserted = len(matched.split()) - len(canonical_tokens)
            if inserted <= 0 or inserted > MAX_INSERTED_NAME_TOKENS:
                continue
            if matched == canonical:
                continue
            span = match.span()
            if span not in seen:
                seen.add(span)
                spans.append((span[0], span[1], "expanded"))

    return sorted(spans, key=lambda item: (item[0], item[1]))


@dataclass(slots=True)
class IdentityMatch:
    status: str
    excerpt: str = ""
    reason: str = ""
    name_position: int | None = None


class IdentityResolver:
    def __init__(self, window_chars: int = 300) -> None:
        self.window_chars = window_chars

    def evaluate(
        self,
        full_text: str,
        full_name: str,
        org_target: str,
    ) -> IdentityMatch:
        if not full_text.strip():
            return IdentityMatch(
                IdentityStatus.REJECTED_NO_NAME.value,
                reason="No source text.",
            )
        if not org_target.strip():
            return IdentityMatch(
                IdentityStatus.REJECTED_NO_CONTEXT.value,
                reason="No organisation context.",
            )

        text_norm = _norm(full_text)
        org_tokens = _org_terms(org_target) or _norm(org_target).split()
        name_spans = find_name_spans(text_norm, full_name)
        if not name_spans:
            return IdentityMatch(
                IdentityStatus.REJECTED_NO_NAME.value,
                reason="No discriminating name variant found.",
            )

        org_norm = _norm(org_target)
        for pos, _name_end, match_kind in name_spans:
            start = max(0, pos - self.window_chars)
            end = min(len(text_norm), pos + self.window_chars)
            window = text_norm[start:end]
            expanded = match_kind == "expanded"

            if org_norm and org_norm in window:
                if expanded:
                    return IdentityMatch(
                        IdentityStatus.ACCEPTED_PROVISIONAL.value,
                        excerpt=window,
                        reason=(
                            "Expanded full-name form and full organisation context "
                            "co-occur within identity window; retained as provisional."
                        ),
                        name_position=pos,
                    )
                return IdentityMatch(
                    IdentityStatus.ACCEPTED.value,
                    excerpt=window,
                    reason=(
                        "Name and full organisation context co-occur within "
                        "identity window."
                    ),
                    name_position=pos,
                )

            matched = [term for term in org_tokens if term in window]
            if matched:
                prefix = "Expanded name" if expanded else "Name"
                return IdentityMatch(
                    IdentityStatus.ACCEPTED_PROVISIONAL.value,
                    excerpt=window,
                    reason=(
                        f"{prefix} co-occurs with organisation token(s): "
                        f"{', '.join(matched[:3])}."
                    ),
                    name_position=pos,
                )

        return IdentityMatch(
            IdentityStatus.REJECTED_NO_COOCCURRENCE.value,
            reason=(
                "Name found, but organisation context did not co-occur in the "
                "identity window."
            ),
        )
