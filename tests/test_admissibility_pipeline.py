from __future__ import annotations

import hashlib

import pandas as pd
import pytest
import requests

from profair_observability.admissibility.batch import run_batch
from profair_observability.admissibility.engine import AdmissibilityEngine
from profair_observability.admissibility.independence import assess_pair
from profair_observability.admissibility.identity import IdentityResolver
from profair_observability.admissibility.privacy import enforce_public_mode
from profair_observability.admissibility.schema import (
    EvaluatedSource,
    IndependenceStatus,
    RetrievedSource,
    RetrievalStatus,
)
from profair_observability.admissibility.search import (
    QueryBuilder,
    SearchProvider,
    SerpAPISearchProvider,
)


def source(url: str, text: str, sha: str | None = None) -> RetrievedSource:
    return RetrievedSource(
        query='"Target Person" "Example Org"',
        provider="test",
        rank=1,
        requested_url=url,
        final_url=url,
        retrieval_status=RetrievalStatus.FULL_TEXT_RETRIEVED.value,
        full_text=text,
        page_title="Example Org",
        content_sha256=sha or hashlib.sha256(text.encode()).hexdigest(),
    )


def test_queries_never_use_preliminary_classification() -> None:
    row = {
        "full_name": "María Example",
        "org_search_target": "Example Org",
        "country_code": "ES",
        "preliminary_classification": "Woman",
    }
    queries = QueryBuilder().build(row)
    assert queries
    assert all("Woman" not in q for q in queries)


def test_identity_requires_nearby_organisation_context() -> None:
    resolver = IdentityResolver(window_chars=120)
    text = (
        "Target Person presented the project. "
        + ("x " * 200)
        + "Example Org sponsors the event."
    )
    match = resolver.evaluate(text, "Target Person", "Example Org")
    assert match.status == "REJECTED_NO_COOCCURRENCE"


def test_official_direct_gendered_evidence_is_admissible() -> None:
    row = {
        "person_id": "PX1",
        "full_name": "Ana Ejemplo",
        "org_search_target": "Ejemplo Uno",
        "organisation_domain": "ejemplouno.org",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [
            source(
                "https://ejemplouno.org/equipo",
                "Ana Ejemplo es directora de innovación de Ejemplo Uno.",
            )
        ],
    )
    assert decision.A_i_B == 1
    assert decision.final_category == "Woman"


def test_single_secondary_source_is_not_admissible() -> None:
    row = {
        "person_id": "PX2",
        "full_name": "Luis Ejemplo",
        "org_search_target": "Ejemplo Dos",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [
            source(
                "https://industrynews.test/interview",
                "Luis Ejemplo es director comercial de Ejemplo Dos.",
            )
        ],
    )
    assert decision.A_i_B == 0
    assert decision.final_category == "Indeterminate"


def test_gender_marker_elsewhere_on_page_is_not_attributed() -> None:
    row = {
        "person_id": "PX3",
        "full_name": "Alex Example",
        "org_search_target": "Example Three",
        "organisation_domain": "examplethree.org",
        "preliminary_classification": "",
    }
    text = (
        "Alex Example works at Example Three on market development. "
        "A separate biography appears here. Maria Other is directora "
        "of another unit."
    )
    decision = AdmissibilityEngine().evaluate(
        row,
        [source("https://examplethree.org/team", text)],
    )
    assert decision.A_i_B == 0
    assert decision.final_category == "Indeterminate"


def test_exact_duplicate_sources_are_not_independent() -> None:
    text = "Target Person is director of Example Org."
    a = EvaluatedSource(
        source("https://a.test/x", text, sha="same"),
        "ACCEPTED",
    )
    b = EvaluatedSource(
        source("https://b.test/y", text, sha="same"),
        "ACCEPTED",
    )
    assert assess_pair(a, b).status == IndependenceStatus.EXACT_DUPLICATE.value


def test_public_mode_rejects_direct_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROFAIR_RESTRICTED_MODE", raising=False)
    with pytest.raises(ValueError):
        enforce_public_mode(["person_id", "full_name", "primary_fair"])


def test_serpapi_timeout_is_recorded_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SerpAPISearchProvider(
        api_key="test-key",
        retries=0,
        min_interval_seconds=0.0,
    )

    def timeout(*args: object, **kwargs: object) -> None:
        raise requests.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(provider.session, "get", timeout)
    assert provider.search('"Target Person" "Example Org"') == []
    assert provider.attempts[-1]["status"] == "TIMEOUT"


class AlwaysFailSearchProvider(SearchProvider):
    name = "always-fail"

    def __init__(self) -> None:
        super().__init__(min_interval_seconds=0.0)

    def search(self, query: str, max_results: int = 5) -> list:
        self._record_attempt(
            query=query,
            status="TIMEOUT",
            error="synthetic timeout",
        )
        return []


def test_all_search_timeouts_are_not_counted_as_not_classified(
    tmp_path: pytest.TempPathFactory,
) -> None:
    df = pd.DataFrame(
        [
            {
                "person_id": "PX_TIMEOUT",
                "full_name": "Target Person",
                "org_search_target": "Example Org",
                "preliminary_classification": "Woman",
            }
        ]
    )
    results, _, manifest = run_batch(
        df,
        provider=AlwaysFailSearchProvider(),
        output_dir=tmp_path,
        max_queries=2,
        checkpoint_every=1,
    )
    assert results.loc[0, "processing_status"] == "TECHNICAL_FAILURE"
    assert results.loc[0, "final_category"] == ""
    assert manifest["summary"]["n_not_classified"] == 0
    assert manifest["summary"]["n_technical_failure"] == 1
