from __future__ import annotations

import re

from unidecode import unidecode

from .schema import EvidenceHit, FinalCategory
from .search import name_variants

MAX_INTERVENING_TOKENS = 4


def _norm_name(text: str) -> str:
    text = unidecode(text or "").casefold()
    return re.sub(r"\s+", " ", text).strip()


def _norm_text(text: str) -> str:
    text = unidecode(text or "").casefold()
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\s{2,}|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 10]


LEXICON = {
    "es": {
        FinalCategory.WOMAN.value: [
            r"\bdirectora\b",
            r"\bpresidenta\b",
            r"\bcoordinadora\b",
            r"\bsecretaria\b",
            r"\bjefa\b",
            r"\bfundadora\b",
            r"\binvestigadora\b",
            r"\bprofesora\b",
            r"\bdiseñadora\b",
            r"\bsra\.?\b",
            r"\bseñora\b",
        ],
        FinalCategory.MAN.value: [
            r"\bdirector\b",
            r"\bpresidente\b",
            r"\bcoordinador\b",
            r"\bsecretario\b",
            r"\bjefe\b",
            r"\bfundador\b",
            r"\binvestigador\b",
            r"\bprofesor\b",
            r"\bdiseñador\b",
            r"\bsr\.?\b",
            r"\bseñor\b",
        ],
    },
    "ca": {
        FinalCategory.WOMAN.value: [
            r"\bdirectora\b",
            r"\bpresidenta\b",
            r"\bcoordinadora\b",
            r"\bsecretària\b",
            r"\bfundadora\b",
            r"\bprofessora\b",
        ],
        FinalCategory.MAN.value: [
            r"\bdirector\b",
            r"\bpresident\b",
            r"\bcoordinador\b",
            r"\bsecretari\b",
            r"\bfundador\b",
            r"\bprofessor\b",
        ],
    },
    "pt": {
        FinalCategory.WOMAN.value: [
            r"\bdiretora\b",
            r"\bcoordenadora\b",
            r"\bsecretária\b",
            r"\bfundadora\b",
            r"\bprofessora\b",
        ],
        FinalCategory.MAN.value: [
            r"\bdiretor\b",
            r"\bcoordenador\b",
            r"\bsecretário\b",
            r"\bfundador\b",
            r"\bprofessor\b",
        ],
    },
    "fr": {
        FinalCategory.WOMAN.value: [
            r"\bdirectrice\b",
            r"\bprésidente\b",
            r"\bcoordinatrice\b",
            r"\bfondatrice\b",
            r"\bprofesseure\b",
            r"\bmme\b",
        ],
        FinalCategory.MAN.value: [
            r"\bdirecteur\b",
            r"\bprésident\b",
            r"\bcoordinateur\b",
            r"\bfondateur\b",
        ],
    },
    "it": {
        FinalCategory.WOMAN.value: [
            r"\bdirettrice\b",
            r"\bcoordinatrice\b",
            r"\bsegretaria\b",
            r"\bfondatrice\b",
            r"\bprofessoressa\b",
            r"\bsignora\b",
        ],
        FinalCategory.MAN.value: [
            r"\bdirettore\b",
            r"\bcoordinatore\b",
            r"\bsegretario\b",
            r"\bfondatore\b",
            r"\bprofessore\b",
            r"\bsignore\b",
        ],
    },
    "de": {
        FinalCategory.WOMAN.value: [
            r"\bdirektorin\b",
            r"\bgeschäftsführerin\b",
            r"\bkoordinatorin\b",
            r"\bgründerin\b",
            r"\bprofessorin\b",
            r"\bfrau\b",
        ],
        FinalCategory.MAN.value: [
            r"\bdirektor\b",
            r"\bgeschäftsführer\b",
            r"\bkoordinator\b",
            r"\bgründer\b",
            r"\bprofessor\b",
            r"\bherr\b",
        ],
    },
    "en": {
        FinalCategory.WOMAN.value: [
            r"\bms\.?\b",
            r"\bmrs\.?\b",
            r"\bwoman\b",
            r"\bfemale\b",
            r"\bchairwoman\b",
            r"\bspokeswoman\b",
            r"\bbusinesswoman\b",
        ],
        FinalCategory.MAN.value: [
            r"\bmr\.?\b",
            r"\bman\b",
            r"\bmale\b",
            r"\bchairman\b",
            r"\bspokesman\b",
            r"\bbusinessman\b",
        ],
    },
}

ALTERNATIVE_PATTERNS = [
    r"\bnon[- ]?binary\b",
    r"\bnon[- ]?binario\b",
    r"\bgenderqueer\b",
]

# Tokens whose surface form is also a common ungendered English title.
# These are admitted only when nearby syntax supplies a language-specific cue.
CROSS_LANGUAGE_AMBIGUOUS = {
    "director": {
        "reject_after": r"^\s+(?:of|for|at|and)\b",
        "require_after": (
            r"^\s+(?:de|del|dels|de\s+la|general|comercial|ejecutivo|"
            r"executiu|tecnico|tecnic|artistico|artistic|titular)\b"
        ),
        "require_before": r"(?:\bel|\bcomo|\bes|\bun)\s*$",
    },
    "president": {
        "reject_after": r"^\s+(?:of|for|at|and)\b",
        "require_after": r"^\s+(?:de|del|dels|de\s+la)\b",
        "require_before": r"(?:\bel|\bcom|\bes)\s*$",
    },
}


def _target_spans(norm_sentence: str, full_name: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for variant in name_variants(full_name):
        target = _norm_name(variant)
        if not target:
            continue
        start = 0
        while True:
            pos = norm_sentence.find(target, start)
            if pos < 0:
                break
            span = (pos, pos + len(target))
            if span not in seen:
                seen.add(span)
                spans.append(span)
            start = pos + max(1, len(target))
    return spans


def _intervening_gap(
    marker_span: tuple[int, int],
    target_span: tuple[int, int],
    text: str,
) -> str:
    marker_start, marker_end = marker_span
    target_start, target_end = target_span
    if marker_end <= target_start:
        return text[marker_end:target_start]
    if target_end <= marker_start:
        return text[target_end:marker_start]
    return ""


def _marker_is_directly_attributable(
    norm_sentence: str,
    marker_span: tuple[int, int],
    target_spans: list[tuple[int, int]],
    marker: str,
) -> bool:
    if not target_spans:
        return False

    gaps = [
        _intervening_gap(marker_span, target_span, norm_sentence)
        for target_span in target_spans
    ]
    gap = min(gaps, key=lambda value: len(re.findall(r"\b\w+\b", value)))
    if len(re.findall(r"\b\w+\b", gap)) > MAX_INTERVENING_TOKENS:
        return False

    marker_key = _norm_text(marker).strip(".")
    rule = CROSS_LANGUAGE_AMBIGUOUS.get(marker_key)
    if rule:
        marker_start, marker_end = marker_span
        before = norm_sentence[max(0, marker_start - 25):marker_start]
        after = norm_sentence[marker_end:marker_end + 50]
        if re.search(rule["reject_after"], after):
            return False
        if not (
            re.search(rule["require_after"], after)
            or re.search(rule["require_before"], before)
        ):
            return False

    return True


class EvidenceExtractor:
    def extract(
        self,
        full_text: str,
        full_name: str,
        source_url: str,
    ) -> list[EvidenceHit]:
        hits: list[EvidenceHit] = []
        seen: set[tuple[str, int, int]] = set()

        for sentence in _sentences(full_text):
            norm_sentence = _norm_text(sentence)
            target_spans = _target_spans(norm_sentence, full_name)
            if not target_spans:
                continue

            for pattern in ALTERNATIVE_PATTERNS:
                ascii_pattern = unidecode(pattern)
                for match in re.finditer(
                    ascii_pattern,
                    norm_sentence,
                    flags=re.IGNORECASE,
                ):
                    if not _marker_is_directly_attributable(
                        norm_sentence,
                        match.span(),
                        target_spans,
                        match.group(0),
                    ):
                        continue
                    key = (
                        FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value,
                        match.start(),
                        match.end(),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(
                        EvidenceHit(
                            FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value,
                            "explicit_self_description",
                            match.group(0),
                            sentence[:600],
                            "local_name_marker_attribution",
                            source_url,
                        )
                    )

            for language, categories in LEXICON.items():
                for category, patterns in categories.items():
                    for pattern in patterns:
                        ascii_pattern = unidecode(pattern)
                        for match in re.finditer(
                            ascii_pattern,
                            norm_sentence,
                            flags=re.IGNORECASE,
                        ):
                            if not _marker_is_directly_attributable(
                                norm_sentence,
                                match.span(),
                                target_spans,
                                match.group(0),
                            ):
                                continue
                            key = (category, match.start(), match.end())
                            if key in seen:
                                continue
                            seen.add(key)
                            hits.append(
                                EvidenceHit(
                                    category,
                                    language,
                                    match.group(0),
                                    sentence[:600],
                                    "local_name_marker_attribution",
                                    source_url,
                                )
                            )

        return hits
