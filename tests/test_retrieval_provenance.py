from __future__ import annotations

import pandas as pd
import pytest

from profair_observability.admissibility.batch import run_batch
from profair_observability.admissibility.retrieval import SourceRetriever
from profair_observability.admissibility.schema import (
    RetrievedSource,
    RetrievalStatus,
    SearchCandidate,
)
from profair_observability.admissibility.search import SearchProvider


class CandidateProvider(SearchProvider):
    name = "candidate-provider"

    def __init__(self, result_count: int = 1) -> None:
        super().__init__(min_interval_seconds=0.0)
        self.result_count = result_count

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchCandidate]:
        count = min(self.result_count, max_results)
        self._record_attempt(
            query=query,
            status="OK",
            result_count=count,
        )
        return [
            SearchCandidate(
                query=query,
                provider=self.name,
                rank=rank,
                url=f"https://example.test/{rank}",
                title=f"Candidate {rank}",
            )
            for rank in range(1, count + 1)
        ]


def audit_row() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "person_id": "PX_RETRIEVAL",
                "full_name": "Target Person",
                "org_search_target": "Example Org",
                "preliminary_classification": "Woman",
            }
        ]
    )


def blocked_record(candidate: SearchCandidate) -> RetrievedSource:
    return RetrievedSource(
        query=candidate.query,
        provider=candidate.provider,
        rank=candidate.rank,
        requested_url=candidate.url,
        final_url=candidate.url,
        retrieval_status=RetrievalStatus.BLOCKED.value,
        http_status=403,
        error_message="HTTP 403",
    )


def test_zero_full_text_retrieval_is_not_not_classified(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_many(
        self: SourceRetriever,
        candidates: list[SearchCandidate],
        use_cache: bool = True,
    ) -> list[RetrievedSource]:
        return [blocked_record(candidate) for candidate in candidates]

    monkeypatch.setattr(SourceRetriever, "fetch_many", fake_fetch_many)
    results, decisions, manifest = run_batch(
        audit_row(),
        provider=CandidateProvider(result_count=1),
        output_dir=tmp_path,
        max_queries=1,
        max_urls_per_person=1,
        checkpoint_every=1,
    )

    assert results.loc[0, "processing_status"] == "TECHNICAL_RETRIEVAL_FAILURE"
    assert results.loc[0, "final_category"] == ""
    assert results.loc[0, "retrieval_error_count"] == 1
    assert manifest["summary"]["n_not_classified"] == 0
    assert manifest["summary"]["n_technical_retrieval_failure"] == 1
    assert decisions[0].search_candidates[0]["url"] == "https://example.test/1"
    assert decisions[0].retrieval_attempts[0]["retrieval_status"] == "BLOCKED"


def test_partial_retrieval_is_flagged_but_decision_is_retained(
    tmp_path: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch_many(
        self: SourceRetriever,
        candidates: list[SearchCandidate],
        use_cache: bool = True,
    ) -> list[RetrievedSource]:
        first = RetrievedSource(
            query=candidates[0].query,
            provider=candidates[0].provider,
            rank=candidates[0].rank,
            requested_url=candidates[0].url,
            final_url=candidates[0].url,
            retrieval_status=RetrievalStatus.FULL_TEXT_RETRIEVED.value,
            full_text="Target Person works for Example Org on market development.",
            page_title="Example Org profile",
            content_sha256="full-text",
        )
        return [first, blocked_record(candidates[1])]

    monkeypatch.setattr(SourceRetriever, "fetch_many", fake_fetch_many)
    results, decisions, manifest = run_batch(
        audit_row(),
        provider=CandidateProvider(result_count=2),
        output_dir=tmp_path,
        max_queries=1,
        max_urls_per_person=2,
        checkpoint_every=1,
    )

    assert results.loc[0, "processing_status"] == "PARTIAL_RETRIEVAL_FAILURE"
    assert results.loc[0, "final_category"] == "Indeterminate"
    assert results.loc[0, "retrieval_error_count"] == 1
    assert manifest["summary"]["n_indeterminate"] == 1
    assert manifest["summary"]["n_partial_retrieval_failure"] == 1
    assert len(decisions[0].retrieval_attempts) == 2
