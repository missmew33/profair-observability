from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .domains import registrable_domain
from .schema import EvaluatedSource, IndependenceStatus

SYNDICATION_HOST_MARKERS = {"businesswire.com", "prnewswire.com", "globenewswire.com", "einpresswire.com"}


def _normalize_for_similarity(text: str, max_chars: int = 6000) -> str:
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñçàèìòùâêîôûäëïöÿß ]+", " ", text)
    return text[:max_chars].strip()


def near_duplicate_similarity(a: str, b: str) -> float:
    na, nb = _normalize_for_similarity(a), _normalize_for_similarity(b)
    return SequenceMatcher(None, na, nb, autojunk=True).ratio() if na and nb else 0.0


@dataclass(slots=True)
class IndependenceAssessment:
    status: str
    reason: str
    similarity: float = 0.0


def assess_pair(a: EvaluatedSource, b: EvaluatedSource, duplicate_threshold: float = 0.84) -> IndependenceAssessment:
    ua, ub = a.source.final_url or a.source.requested_url, b.source.final_url or b.source.requested_url
    da, db = registrable_domain(ua), registrable_domain(ub)
    if da and da == db:
        return IndependenceAssessment(IndependenceStatus.SAME_DOMAIN.value, "Same registrable domain.")
    if a.source.content_sha256 and b.source.content_sha256 and a.source.content_sha256 == b.source.content_sha256:
        return IndependenceAssessment(IndependenceStatus.EXACT_DUPLICATE.value, "Exact content SHA-256 duplicate.", 1.0)
    sim = near_duplicate_similarity(a.source.full_text, b.source.full_text)
    if sim >= duplicate_threshold:
        return IndependenceAssessment(IndependenceStatus.LIKELY_DUPLICATE.value, f"Near-duplicate content similarity {sim:.3f} >= {duplicate_threshold:.2f}.", sim)
    if da in SYNDICATION_HOST_MARKERS or db in SYNDICATION_HOST_MARKERS:
        if da in SYNDICATION_HOST_MARKERS and db in SYNDICATION_HOST_MARKERS:
            return IndependenceAssessment(IndependenceStatus.SYNDICATED.value, "Both sources are press-release wire services.", sim)
        return IndependenceAssessment(IndependenceStatus.UNDETERMINED.value, "One source is a press-release wire service; provenance may be syndicated.", sim)
    if da and db and da != db:
        return IndependenceAssessment(IndependenceStatus.INDEPENDENT.value, f"Different registrable domains and non-duplicate content (similarity {sim:.3f}).", sim)
    return IndependenceAssessment(IndependenceStatus.UNDETERMINED.value, "Insufficient provenance information.", sim)


def find_independent_concordant_pair(sources: list[EvaluatedSource], category: str) -> tuple[bool, str]:
    eligible = [s for s in sources if any(hit.category == category for hit in s.evidence_hits)]
    for i, left in enumerate(eligible):
        for right in eligible[i + 1:]:
            assessment = assess_pair(left, right)
            if assessment.status == IndependenceStatus.INDEPENDENT.value:
                return True, assessment.reason
    return False, "No pair of attributable, concordant, independent professional sources found."
