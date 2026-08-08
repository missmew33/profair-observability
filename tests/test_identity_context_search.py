from __future__ import annotations

from profair_observability.admissibility.engine import AdmissibilityEngine
from profair_observability.admissibility.schema import (
    RetrievedSource,
    RetrievalStatus,
    SearchCandidate,
)
from profair_observability.admissibility.search import (
    QueryBuilder,
    SearchProvider,
    collect_candidates,
    organisation_aliases,
    weak_identity_aliases,
)


def source(text: str) -> RetrievedSource:
    return RetrievedSource(
        query='"Target Person" "Atlantis"',
        provider="test",
        rank=1,
        requested_url="https://news.test/profile",
        final_url="https://news.test/profile",
        retrieval_status=RetrievalStatus.FULL_TEXT_RETRIEVED.value,
        full_text=text,
        page_title="Profile",
        content_sha256="synthetic",
    )


def test_materially_more_specific_account_makes_short_target_weak() -> None:
    row = {
        "org_search_target": "Atlantis",
        "account_name": "Embassy of the Republic of Atlantis",
        "trade_name": "Atlantis",
    }
    assert organisation_aliases(row) == [
        "Atlantis",
        "Embassy of the Republic of Atlantis",
    ]
    assert weak_identity_aliases(row) == {"atlantis"}


def test_legal_suffix_only_does_not_make_brand_alias_weak() -> None:
    row = {
        "org_search_target": "Visit Arcadia",
        "account_name": "Visit Arcadia Corporation",
        "trade_name": "Visit Arcadia",
    }
    assert weak_identity_aliases(row) == set()


def test_exact_match_on_weak_alias_is_only_provisional() -> None:
    row = {
        "person_id": "PX_WEAK",
        "full_name": "Target Person",
        "org_search_target": "Atlantis",
        "account_name": "Embassy of the Republic of Atlantis",
        "trade_name": "Atlantis",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [source("Target Person represented Atlantis at an international event.")],
    )
    assert decision.accepted_identity_count == 0
    assert decision.provisional_identity_count == 1
    assert decision.identity_resolved is False
    assert decision.final_category == "Not Classified"


def test_specific_account_alias_can_resolve_identity() -> None:
    row = {
        "person_id": "PX_SPECIFIC",
        "full_name": "Target Person",
        "org_search_target": "Atlantis",
        "account_name": "Embassy of the Republic of Atlantis",
        "trade_name": "Atlantis",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [
            source(
                "Target Person works for the Embassy of the Republic of Atlantis "
                "on international tourism promotion."
            )
        ],
    )
    assert decision.accepted_identity_count == 1
    assert decision.identity_resolved is True
    assert decision.final_category == "Indeterminate"


def test_query_builder_prioritises_distinct_organisation_aliases() -> None:
    row = {
        "full_name": "Target Person",
        "org_search_target": "Atlantis",
        "account_name": "Embassy of the Republic of Atlantis",
        "trade_name": "Atlantis Tourism",
        "country_code": "AT",
    }
    queries = QueryBuilder(max_queries=3).build(row)
    assert queries == [
        '"Target Person" "Atlantis"',
        '"Target Person" "Embassy of the Republic of Atlantis"',
        '"Target Person" "Atlantis Tourism"',
    ]


class RecordingProvider(SearchProvider):
    name = "recording"

    def __init__(self) -> None:
        super().__init__(min_interval_seconds=0.0)
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchCandidate]:
        self.calls.append((query, max_results))
        return [
            SearchCandidate(
                query=query,
                provider=self.name,
                rank=rank,
                url=f"https://example.test/{len(self.calls)}/{rank}",
            )
            for rank in range(1, max_results + 1)
        ]


def test_candidate_budget_is_distributed_across_queries() -> None:
    provider = RecordingProvider()
    candidates = collect_candidates(
        provider,
        ["q1", "q2", "q3"],
        max_results_per_query=5,
        max_urls=5,
    )
    assert len(candidates) == 5
    assert [call[0] for call in provider.calls] == ["q1", "q2", "q3"]
    assert all(call[1] == 2 for call in provider.calls)
