from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class RetrievalStatus(StrEnum):
    FULL_TEXT_RETRIEVED = "FULL_TEXT_RETRIEVED"
    SEARCH_SNIPPET_ONLY = "SEARCH_SNIPPET_ONLY"
    HTTP_ERROR = "HTTP_ERROR"
    TIMEOUT = "TIMEOUT"
    NON_TEXT_RESOURCE = "NON_TEXT_RESOURCE"
    CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"
    JS_OR_EMPTY_PAGE = "JS_OR_EMPTY_PAGE"
    BLOCKED = "BLOCKED"
    INVALID_URL = "INVALID_URL"


class IdentityStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_PROVISIONAL = "ACCEPTED_PROVISIONAL"
    REJECTED_NO_NAME = "REJECTED_NO_NAME"
    REJECTED_NO_CONTEXT = "REJECTED_NO_CONTEXT"
    REJECTED_NO_COOCCURRENCE = "REJECTED_NO_COOCCURRENCE"
    REJECTED_HOMONYM_RISK = "REJECTED_HOMONYM_RISK"


class SourceType(StrEnum):
    ORGANISATION_OFFICIAL = "ORGANISATION_OFFICIAL"
    INSTITUTIONAL_OFFICIAL = "INSTITUTIONAL_OFFICIAL"
    FAIR_ORGANISER_OFFICIAL = "FAIR_ORGANISER_OFFICIAL"
    PROFESSIONAL_ASSOCIATION_OFFICIAL = "PROFESSIONAL_ASSOCIATION_OFFICIAL"
    OFFICIAL_AUTO_HIGH = "OFFICIAL_AUTO_HIGH"
    OFFICIAL_CANDIDATE = "OFFICIAL_CANDIDATE"
    PROFESSIONAL_NETWORK = "PROFESSIONAL_NETWORK"
    PROFESSIONAL_SECONDARY = "PROFESSIONAL_SECONDARY"
    SEARCH_SNIPPET_ONLY = "SEARCH_SNIPPET_ONLY"
    UNKNOWN = "UNKNOWN"


class OrganisationDomainStatus(StrEnum):
    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"
    UNKNOWN = "UNKNOWN"


class IndependenceStatus(StrEnum):
    INDEPENDENT = "INDEPENDENT"
    SAME_DOMAIN = "SAME_DOMAIN"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    LIKELY_DUPLICATE = "LIKELY_DUPLICATE"
    SYNDICATED = "SYNDICATED"
    UNDETERMINED = "UNDETERMINED"


class FinalCategory(StrEnum):
    WOMAN = "Woman"
    MAN = "Man"
    INDETERMINATE = "Indeterminate"
    NOT_CLASSIFIED = "Not Classified"
    ALTERNATIVE_SELF_DESCRIPTION = "Alternative self-description"


@dataclass(slots=True)
class SearchCandidate:
    query: str
    provider: str
    rank: int
    url: str
    title: str = ""
    snippet: str = ""


@dataclass(slots=True)
class RetrievedSource:
    query: str
    provider: str
    rank: int
    requested_url: str
    final_url: str = ""
    retrieved_at: str = ""
    retrieval_status: str = RetrievalStatus.INVALID_URL.value
    http_status: int | None = None
    content_type: str = ""
    content_sha256: str = ""
    full_text: str = ""
    page_title: str = ""
    source_type: str = SourceType.UNKNOWN.value
    source_type_confidence: float = 0.0
    source_type_reason: str = ""
    from_cache: bool = False
    error_message: str = ""


@dataclass(slots=True)
class EvidenceHit:
    category: str
    language: str
    marker: str
    evidence_excerpt: str
    attribution_rule: str
    source_url: str


@dataclass(slots=True)
class EvaluatedSource:
    source: RetrievedSource
    identity_status: str
    identity_excerpt: str = ""
    identity_reason: str = ""
    evidence_hits: list[EvidenceHit] = field(default_factory=list)


@dataclass(slots=True)
class PersonDecision:
    person_id: str
    audit_case_id: str = ""
    full_name: str = ""
    org_search_target: str = ""
    primary_fair: str = ""
    organisation_domain: str = ""
    organisation_domain_status: str = OrganisationDomainStatus.UNKNOWN.value
    candidate_organisation_domains: list[str] = field(default_factory=list)
    identity_resolved: bool = False
    identity_resolution_rule: str = ""
    accepted_identity_count: int = 0
    provisional_identity_count: int = 0
    identity_source_independence_status: str = IndependenceStatus.UNDETERMINED.value
    A_i_B: int = 0
    final_category: str = FinalCategory.NOT_CLASSIFIED.value
    decision_rule: str = ""
    screening_conflict: bool = False
    source_independence_status: str = IndependenceStatus.UNDETERMINED.value
    qualifying_official_count: int = 0
    qualifying_professional_count: int = 0
    evidence_source_count: int = 0
    processing_status: str = "COMPLETED"
    search_attempt_count: int = 0
    search_error_count: int = 0
    search_attempts: list[dict[str, Any]] = field(default_factory=list)
    sources: list[EvaluatedSource] = field(default_factory=list)

    def to_flat_dict(self) -> dict[str, Any]:
        return {
            "person_id": self.person_id,
            "audit_case_id": self.audit_case_id,
            "full_name": self.full_name,
            "org_search_target": self.org_search_target,
            "primary_fair": self.primary_fair,
            "organisation_domain": self.organisation_domain,
            "organisation_domain_status": self.organisation_domain_status,
            "candidate_organisation_domains": ";".join(
                self.candidate_organisation_domains
            ),
            "identity_resolved": self.identity_resolved,
            "identity_resolution_rule": self.identity_resolution_rule,
            "accepted_identity_count": self.accepted_identity_count,
            "provisional_identity_count": self.provisional_identity_count,
            "identity_source_independence_status": (
                self.identity_source_independence_status
            ),
            "A_i_B": self.A_i_B,
            "final_category": self.final_category,
            "decision_rule": self.decision_rule,
            "screening_conflict": self.screening_conflict,
            "source_independence_status": self.source_independence_status,
            "qualifying_official_count": self.qualifying_official_count,
            "qualifying_professional_count": self.qualifying_professional_count,
            "evidence_source_count": self.evidence_source_count,
            "processing_status": self.processing_status,
            "search_attempt_count": self.search_attempt_count,
            "search_error_count": self.search_error_count,
        }

    def to_provenance_dict(self) -> dict[str, Any]:
        return asdict(self)


REQUIRED_INPUT_FIELDS = {"person_id", "full_name", "org_search_target"}
