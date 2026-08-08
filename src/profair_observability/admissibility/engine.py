from __future__ import annotations

from collections import Counter

from .domains import registrable_domain
from .evidence import EvidenceExtractor
from .identity import IdentityResolver
from .independence import assess_pair, find_independent_concordant_pair
from .schema import (
    EvaluatedSource,
    FinalCategory,
    IdentityStatus,
    IndependenceStatus,
    OrganisationDomainStatus,
    PersonDecision,
    RetrievedSource,
    RetrievalStatus,
    SourceType,
)
from .source_typing import classify_source

STRICT_OFFICIAL_TYPES = {
    SourceType.ORGANISATION_OFFICIAL.value,
    SourceType.INSTITUTIONAL_OFFICIAL.value,
    SourceType.FAIR_ORGANISER_OFFICIAL.value,
    SourceType.PROFESSIONAL_ASSOCIATION_OFFICIAL.value,
}


def _normalise_domain_status(value: object) -> str:
    status = str(value or "").strip().upper()
    allowed = {item.value for item in OrganisationDomainStatus}
    return status if status in allowed else OrganisationDomainStatus.UNKNOWN.value


def _independent_provisional_pair(
    sources: list[EvaluatedSource],
) -> tuple[list[EvaluatedSource], str]:
    for index, left in enumerate(sources):
        for right in sources[index + 1 :]:
            assessment = assess_pair(left, right)
            if assessment.status == IndependenceStatus.INDEPENDENT.value:
                return [left, right], assessment.reason
    return [], "No independent pair of provisional identity sources found."


def _candidate_domains(sources: list[EvaluatedSource]) -> list[str]:
    candidate_types = {
        SourceType.OFFICIAL_AUTO_HIGH.value,
        SourceType.OFFICIAL_CANDIDATE.value,
    }
    domains = {
        registrable_domain(item.source.final_url or item.source.requested_url)
        for item in sources
        if item.source.source_type in candidate_types
    }
    return sorted(domain for domain in domains if domain)


class AdmissibilityEngine:
    def __init__(
        self,
        *,
        identity_window_chars: int = 300,
        allow_auto_official_high: bool = False,
        trusted_official_domains: set[str] | None = None,
    ) -> None:
        self.identity = IdentityResolver(window_chars=identity_window_chars)
        self.evidence = EvidenceExtractor()
        self.allow_auto_official_high = allow_auto_official_high
        self.trusted_official_domains = trusted_official_domains or set()

    def _official_types(self) -> set[str]:
        types = set(STRICT_OFFICIAL_TYPES)
        if self.allow_auto_official_high:
            types.add(SourceType.OFFICIAL_AUTO_HIGH.value)
        return types

    def evaluate(
        self,
        row: dict,
        retrieved_sources: list[RetrievedSource],
    ) -> PersonDecision:
        person_id = str(row.get("person_id", ""))
        audit_case_id = str(row.get("audit_case_id", "") or "")
        full_name = str(row.get("full_name", "") or "").strip()
        org_target = str(row.get("org_search_target", "") or "").strip()
        primary_fair = str(row.get("primary_fair", "") or "")
        organisation_domain = str(row.get("organisation_domain", "") or "").strip()
        organisation_domain_status = _normalise_domain_status(
            row.get("organisation_domain_status", "")
        )
        preliminary = str(row.get("preliminary_classification", "") or "").strip()

        evaluated: list[EvaluatedSource] = []
        for source in retrieved_sources:
            if source.retrieval_status != RetrievalStatus.FULL_TEXT_RETRIEVED.value:
                continue
            classify_source(
                source,
                org_target=org_target,
                organisation_domain=organisation_domain,
                organisation_domain_status=organisation_domain_status,
                trusted_official_domains=self.trusted_official_domains,
            )
            identity_match = self.identity.evaluate(
                source.full_text,
                full_name,
                org_target,
            )
            hits = []
            if identity_match.status in {
                IdentityStatus.ACCEPTED.value,
                IdentityStatus.ACCEPTED_PROVISIONAL.value,
            }:
                hits = self.evidence.extract(
                    source.full_text,
                    full_name,
                    source.final_url or source.requested_url,
                )
            evaluated.append(
                EvaluatedSource(
                    source=source,
                    identity_status=identity_match.status,
                    identity_excerpt=identity_match.excerpt,
                    identity_reason=identity_match.reason,
                    evidence_hits=hits,
                )
            )

        strong = [
            item
            for item in evaluated
            if item.identity_status == IdentityStatus.ACCEPTED.value
        ]
        provisional = [
            item
            for item in evaluated
            if item.identity_status == IdentityStatus.ACCEPTED_PROVISIONAL.value
        ]
        provisional_pair, provisional_pair_reason = _independent_provisional_pair(
            provisional
        )

        if strong:
            identity_resolved = True
            identity_resolution_rule = "accepted_identity_source"
            identity_independence = IndependenceStatus.UNDETERMINED.value
            identity_evidence_sources = strong
        elif provisional_pair:
            identity_resolved = True
            identity_resolution_rule = (
                "two_independent_provisional_identity_sources"
            )
            identity_independence = IndependenceStatus.INDEPENDENT.value
            identity_evidence_sources = provisional_pair
        else:
            identity_resolved = False
            identity_resolution_rule = (
                "identity_only_provisionally_resolved"
                if provisional
                else "identity_not_resolved"
            )
            identity_independence = IndependenceStatus.UNDETERMINED.value
            identity_evidence_sources = []

        base = {
            "person_id": person_id,
            "audit_case_id": audit_case_id,
            "full_name": full_name,
            "org_search_target": org_target,
            "primary_fair": primary_fair,
            "organisation_domain": organisation_domain,
            "organisation_domain_status": organisation_domain_status,
            "candidate_organisation_domains": _candidate_domains(evaluated),
            "identity_resolved": identity_resolved,
            "identity_resolution_rule": identity_resolution_rule,
            "accepted_identity_count": len(strong),
            "provisional_identity_count": len(provisional),
            "identity_source_independence_status": identity_independence,
            "sources": evaluated,
        }

        if not identity_resolved:
            decision = PersonDecision(
                **base,
                A_i_B=0,
                final_category=FinalCategory.NOT_CLASSIFIED.value,
                decision_rule=identity_resolution_rule,
                evidence_source_count=0,
            )
            return self._screening_flag(decision, preliminary)

        evidence_sources = [
            item for item in identity_evidence_sources if item.evidence_hits
        ]
        categories = Counter(
            hit.category
            for source in evidence_sources
            for hit in source.evidence_hits
        )

        if categories.get(FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value, 0) > 0:
            decision = PersonDecision(
                **base,
                A_i_B=0,
                final_category=FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value,
                decision_rule="explicit_alternative_self_description",
                evidence_source_count=len(evidence_sources),
            )
            return self._screening_flag(decision, preliminary)

        has_woman = categories.get(FinalCategory.WOMAN.value, 0) > 0
        has_man = categories.get(FinalCategory.MAN.value, 0) > 0
        if has_woman and has_man:
            decision = PersonDecision(
                **base,
                A_i_B=0,
                final_category=FinalCategory.INDETERMINATE.value,
                decision_rule="conflicting_attributable_gender_evidence",
                evidence_source_count=len(evidence_sources),
            )
            return self._screening_flag(decision, preliminary)

        if not has_woman and not has_man:
            decision = PersonDecision(
                **base,
                A_i_B=0,
                final_category=FinalCategory.INDETERMINATE.value,
                decision_rule="identity_resolved_but_no_admissible_gender_evidence",
                evidence_source_count=0,
            )
            return self._screening_flag(decision, preliminary)

        target_category = (
            FinalCategory.WOMAN.value if has_woman else FinalCategory.MAN.value
        )
        official_types = self._official_types()
        qualifying_official = [
            item
            for item in evidence_sources
            if item.source.source_type in official_types
            and any(hit.category == target_category for hit in item.evidence_hits)
        ]
        excluded_unverified = {
            SourceType.OFFICIAL_CANDIDATE.value,
        }
        if not self.allow_auto_official_high:
            excluded_unverified.add(SourceType.OFFICIAL_AUTO_HIGH.value)
        professional = [
            item
            for item in evidence_sources
            if item.source.source_type not in official_types
            and item.source.source_type not in excluded_unverified
            and any(hit.category == target_category for hit in item.evidence_hits)
        ]

        if qualifying_official:
            decision = PersonDecision(
                **base,
                A_i_B=1,
                final_category=target_category,
                decision_rule=(
                    "official_source_with_attributable_unambiguous_evidence"
                ),
                source_independence_status=IndependenceStatus.UNDETERMINED.value,
                qualifying_official_count=len(qualifying_official),
                qualifying_professional_count=len(professional),
                evidence_source_count=len(evidence_sources),
            )
            return self._screening_flag(decision, preliminary)

        independent_pair, reason = find_independent_concordant_pair(
            professional,
            target_category,
        )
        if independent_pair:
            decision = PersonDecision(
                **base,
                A_i_B=1,
                final_category=target_category,
                decision_rule="two_independent_concordant_professional_sources",
                source_independence_status=IndependenceStatus.INDEPENDENT.value,
                qualifying_official_count=0,
                qualifying_professional_count=len(professional),
                evidence_source_count=len(evidence_sources),
            )
            return self._screening_flag(decision, preliminary)

        if provisional_pair and not strong:
            reason = f"{reason} Identity gate: {provisional_pair_reason}"
        decision = PersonDecision(
            **base,
            A_i_B=0,
            final_category=FinalCategory.INDETERMINATE.value,
            decision_rule=f"insufficient_primary_evidence: {reason}",
            qualifying_official_count=0,
            qualifying_professional_count=len(professional),
            evidence_source_count=len(evidence_sources),
        )
        return self._screening_flag(decision, preliminary)

    @staticmethod
    def _screening_flag(
        decision: PersonDecision,
        preliminary: str,
    ) -> PersonDecision:
        if decision.A_i_B == 1 and preliminary in {
            FinalCategory.WOMAN.value,
            FinalCategory.MAN.value,
        }:
            decision.screening_conflict = preliminary != decision.final_category
        else:
            decision.screening_conflict = False
        assert not (
            decision.A_i_B == 1
            and decision.final_category
            not in {FinalCategory.WOMAN.value, FinalCategory.MAN.value}
        )
        return decision
