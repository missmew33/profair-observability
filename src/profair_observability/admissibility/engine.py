from __future__ import annotations

from collections import Counter

from .evidence import EvidenceExtractor
from .identity import IdentityResolver
from .independence import find_independent_concordant_pair
from .schema import EvaluatedSource, FinalCategory, IdentityStatus, IndependenceStatus, PersonDecision, RetrievedSource, RetrievalStatus, SourceType
from .source_typing import classify_source

STRICT_OFFICIAL_TYPES = {SourceType.ORGANISATION_OFFICIAL.value, SourceType.INSTITUTIONAL_OFFICIAL.value, SourceType.FAIR_ORGANISER_OFFICIAL.value, SourceType.PROFESSIONAL_ASSOCIATION_OFFICIAL.value}


class AdmissibilityEngine:
    def __init__(self, *, identity_window_chars: int = 300, allow_auto_official_high: bool = False, trusted_official_domains: set[str] | None = None) -> None:
        self.identity = IdentityResolver(window_chars=identity_window_chars)
        self.evidence = EvidenceExtractor()
        self.allow_auto_official_high = allow_auto_official_high
        self.trusted_official_domains = trusted_official_domains or set()

    def _official_types(self) -> set[str]:
        types = set(STRICT_OFFICIAL_TYPES)
        if self.allow_auto_official_high:
            types.add(SourceType.OFFICIAL_AUTO_HIGH.value)
        return types

    def evaluate(self, row: dict, retrieved_sources: list[RetrievedSource]) -> PersonDecision:
        person_id = str(row.get("person_id", ""))
        audit_case_id = str(row.get("audit_case_id", "") or "")
        full_name = str(row.get("full_name", "") or "").strip()
        org_target = str(row.get("org_search_target", "") or "").strip()
        primary_fair = str(row.get("primary_fair", "") or "")
        organisation_domain = str(row.get("organisation_domain", "") or "").strip()
        preliminary = str(row.get("preliminary_classification", "") or "").strip()

        evaluated = []
        for source in retrieved_sources:
            if source.retrieval_status != RetrievalStatus.FULL_TEXT_RETRIEVED.value:
                continue
            classify_source(source, org_target=org_target, organisation_domain=organisation_domain, trusted_official_domains=self.trusted_official_domains)
            identity_match = self.identity.evaluate(source.full_text, full_name, org_target)
            hits = []
            if identity_match.status in {IdentityStatus.ACCEPTED.value, IdentityStatus.ACCEPTED_PROVISIONAL.value}:
                hits = self.evidence.extract(source.full_text, full_name, source.final_url or source.requested_url)
            evaluated.append(EvaluatedSource(source=source, identity_status=identity_match.status, identity_excerpt=identity_match.excerpt, identity_reason=identity_match.reason, evidence_hits=hits))

        resolved = [s for s in evaluated if s.identity_status in {IdentityStatus.ACCEPTED.value, IdentityStatus.ACCEPTED_PROVISIONAL.value}]
        strongly_resolved = [s for s in evaluated if s.identity_status == IdentityStatus.ACCEPTED.value]
        evidence_sources = [s for s in strongly_resolved if s.evidence_hits]
        categories = Counter(hit.category for source in evidence_sources for hit in source.evidence_hits)

        if categories.get(FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value, 0) > 0:
            return self._screening_flag(PersonDecision(person_id=person_id, audit_case_id=audit_case_id, full_name=full_name, org_search_target=org_target, primary_fair=primary_fair, identity_resolved=bool(resolved), A_i_B=0, final_category=FinalCategory.ALTERNATIVE_SELF_DESCRIPTION.value, decision_rule="explicit_alternative_self_description", evidence_source_count=len(evidence_sources), sources=evaluated), preliminary)

        has_woman = categories.get(FinalCategory.WOMAN.value, 0) > 0
        has_man = categories.get(FinalCategory.MAN.value, 0) > 0
        if has_woman and has_man:
            return self._screening_flag(PersonDecision(person_id=person_id, audit_case_id=audit_case_id, full_name=full_name, org_search_target=org_target, primary_fair=primary_fair, identity_resolved=bool(resolved), A_i_B=0, final_category=FinalCategory.INDETERMINATE.value, decision_rule="conflicting_attributable_gender_evidence", evidence_source_count=len(evidence_sources), sources=evaluated), preliminary)

        if not has_woman and not has_man:
            category = FinalCategory.INDETERMINATE.value if resolved else FinalCategory.NOT_CLASSIFIED.value
            rule = "identity_resolved_but_no_admissible_gender_evidence" if resolved else "identity_not_resolved"
            return self._screening_flag(PersonDecision(person_id=person_id, audit_case_id=audit_case_id, full_name=full_name, org_search_target=org_target, primary_fair=primary_fair, identity_resolved=bool(resolved), A_i_B=0, final_category=category, decision_rule=rule, evidence_source_count=0, sources=evaluated), preliminary)

        target_category = FinalCategory.WOMAN.value if has_woman else FinalCategory.MAN.value
        official_types = self._official_types()
        qualifying_official = [s for s in evidence_sources if s.source.source_type in official_types and any(hit.category == target_category for hit in s.evidence_hits)]
        professional = [s for s in evidence_sources if s.source.source_type not in official_types and s.source.source_type != SourceType.OFFICIAL_CANDIDATE.value and any(hit.category == target_category for hit in s.evidence_hits)]

        if qualifying_official:
            return self._screening_flag(PersonDecision(person_id=person_id, audit_case_id=audit_case_id, full_name=full_name, org_search_target=org_target, primary_fair=primary_fair, identity_resolved=True, A_i_B=1, final_category=target_category, decision_rule="official_source_with_attributable_unambiguous_evidence", source_independence_status=IndependenceStatus.UNDETERMINED.value, qualifying_official_count=len(qualifying_official), qualifying_professional_count=len(professional), evidence_source_count=len(evidence_sources), sources=evaluated), preliminary)

        independent_pair, reason = find_independent_concordant_pair(professional, target_category)
        if independent_pair:
            return self._screening_flag(PersonDecision(person_id=person_id, audit_case_id=audit_case_id, full_name=full_name, org_search_target=org_target, primary_fair=primary_fair, identity_resolved=True, A_i_B=1, final_category=target_category, decision_rule="two_independent_concordant_professional_sources", source_independence_status=IndependenceStatus.INDEPENDENT.value, qualifying_official_count=0, qualifying_professional_count=len(professional), evidence_source_count=len(evidence_sources), sources=evaluated), preliminary)

        return self._screening_flag(PersonDecision(person_id=person_id, audit_case_id=audit_case_id, full_name=full_name, org_search_target=org_target, primary_fair=primary_fair, identity_resolved=True, A_i_B=0, final_category=FinalCategory.INDETERMINATE.value, decision_rule=f"insufficient_primary_evidence: {reason}", qualifying_official_count=0, qualifying_professional_count=len(professional), evidence_source_count=len(evidence_sources), sources=evaluated), preliminary)

    @staticmethod
    def _screening_flag(decision: PersonDecision, preliminary: str) -> PersonDecision:
        if decision.A_i_B == 1 and preliminary in {FinalCategory.WOMAN.value, FinalCategory.MAN.value}:
            decision.screening_conflict = preliminary != decision.final_category
        else:
            decision.screening_conflict = False
        assert not (decision.A_i_B == 1 and decision.final_category not in {FinalCategory.WOMAN.value, FinalCategory.MAN.value})
        return decision
