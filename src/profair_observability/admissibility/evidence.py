from __future__ import annotations

import re

from unidecode import unidecode

from .schema import EvidenceHit, FinalCategory
from .search import name_variants


def _norm_name(text: str) -> str:
    text = unidecode(text or "").casefold()
    return re.sub(r"\s+", " ", text).strip()


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\s{2,}|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 10]


LEXICON = {
    "es": {
        FinalCategory.WOMAN.value: [r"\bdirectora\b", r"\bpresidenta\b", r"\bcoordinadora\b", r"\bsecretaria\b", r"\bjefa\b", r"\bfundadora\b", r"\binvestigadora\b", r"\bprofesora\b", r"\bdiseñadora\b", r"\bsra\.?\b", r"\bseñora\b"],
        FinalCategory.MAN.value: [r"\bdirector\b", r"\bpresidente\b", r"\bcoordinador\b", r"\bsecretario\b", r"\bjefe\b", r"\bfundador\b", r"\binvestigador\b", r"\bprofesor\b", r"\bdiseñador\b", r"\bsr\.?\b", r"\bseñor\b"],
    },
    "pt": {
        FinalCategory.WOMAN.value: [r"\bdiretora\b", r"\bcoordenadora\b", r"\bsecretária\b", r"\bfundadora\b", r"\bprofessora\b"],
        FinalCategory.MAN.value: [r"\bdiretor\b", r"\bcoordenador\b", r"\bsecretário\b", r"\bfundador\b", r"\bprofessor\b"],
    },
    "fr": {
        FinalCategory.WOMAN.value: [r"\bdirectrice\b", r"\bprésidente\b", r"\bcoordinatrice\b", r"\bfondatrice\b", r"\bprofesseure\b", r"\bmme\b"],
        FinalCategory.MAN.value: [r"\bdirecteur\b", r"\bprésident\b", r"\bcoordinateur\b", r"\bfondateur\b", r"\bprofesseur\b"],
    },
    "it": {
        FinalCategory.WOMAN.value: [r"\bdirettrice\b", r"\bcoordinatrice\b", r"\bsegretaria\b", r"\bfondatrice\b", r"\bprofessoressa\b", r"\bsignora\b"],
        FinalCategory.MAN.value: [r"\bdirettore\b", r"\bcoordinatore\b", r"\bsegretario\b", r"\bfondatore\b", r"\bprofessore\b", r"\bsignore\b"],
    },
    "de": {
        FinalCategory.WOMAN.value: [r"\bdirektorin\b", r"\bgeschäftsführerin\b", r"\bkoordinatorin\b", r"\bgründerin\b", r"\bprofessorin\b", r"\bfrau\b"],
        FinalCategory.MAN.value: [r"\bdirektor\b", r"\bgeschäftsführer\b", r"\bkoordinator\b", r"\bgründer\b", r"\bprofessor\b", r"\bherr\b"],
    },
    "en": {
        FinalCategory.WOMAN.value: [r"\bms\.?\b", r"\bmrs\.?\b", r"\bwoman\b", r"\bfemale\b", r"\bchairwoman\b", r"\bspokeswoman\b", r"\bbusinesswoman\b"],
        FinalCategory.MAN.value: [r"\bmr\.?\b", r"\bman\b", r"\bmale\b", r"\bchairman\b", r"\bspokesman\b", r"\bbusinessman\b"],
    },
}

ALTERNATIVE_PATTERNS = [r"\bnon[- ]?binary\b", r"\bnon[- ]?binario\b", r"\bgenderqueer\b"]


class EvidenceExtractor:
    def extract(self, full_text: str, full_name: str, source_url: str) -> list[EvidenceHit]:
        variants = [_norm_name(v) for v in name_variants(full_name)]
        hits, seen = [], set()
        for sentence in _sentences(full_text):
            if not any(v and v in _norm_name(sentence) for v in variants):
                continue
            norm_sentence = _norm_text(sentence)
            for pattern in ALTERNATIVE_PATTERNS:
                match = re.search(pattern, norm_sentence, flags=re.IGNORECASE)
                if match:
                    key = (FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value, "alt", match.group(0))
                    if key not in seen:
                        seen.add(key)
                        hits.append(EvidenceHit(FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value, "explicit_self_description", match.group(0), sentence[:600], "same_sentence_name_and_explicit_alternative_description", source_url))
            for language, categories in LEXICON.items():
                for category, patterns in categories.items():
                    for pattern in patterns:
                        match = re.search(pattern, norm_sentence, flags=re.IGNORECASE)
                        if match:
                            key = (category, language, match.group(0).casefold())
                            if key not in seen:
                                seen.add(key)
                                hits.append(EvidenceHit(category, language, match.group(0), sentence[:600], "same_sentence_name_and_unambiguous_marker", source_url))
        return hits
