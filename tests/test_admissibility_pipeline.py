from __future__ import annotations

import hashlib

import pandas as pd
import pytest
import requests

from profair_observability.admissibility.batch import run_batch
from profair_observability.admissibility.engine import AdmissibilityEngine
from profair_observability.admissibility.evidence import EvidenceExtractor
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
    assert all("Woman" not in query for query in queries)


def test_identity_requires_nearby_organisation_context() -> None:
    resolver = IdentityResolver(window_chars=120)
    text = (
        "Target Person presented the project. "
        + ("x " * 200)
        + "Example Org sponsors the event."
    )
    match = resolver.evaluate(text, "Target Person", "Example Org")
    assert match.status == "REJECTED_NO_COOCCURRENCE"


def test_verified_official_direct_gendered_evidence_is_admissible() -> None:
    row = {
        "person_id": "PX1",
        "full_name": "Ana Ejemplo",
        "org_search_target": "Ejemplo Uno",
        "organisation_domain": "ejemplouno.org",
        "organisation_domain_status": "VERIFIED",
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


def test_unverified_supplied_domain_is_not_primary_evidence() -> None:
    row = {
        "person_id": "PX_DOMAIN",
        "full_name": "Ana Ejemplo",
        "org_search_target": "Ejemplo Uno",
        "organisation_domain": "ejemplouno.org",
        "organisation_domain_status": "CANDIDATE",
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
    assert decision.identity_resolved is True
    assert decision.A_i_B == 0
    assert decision.final_category == "Indeterminate"
    assert decision.candidate_organisation_domains == ["ejemplouno.org"]


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


def test_single_provisional_identity_is_not_resolved() -> None:
    row = {
        "person_id": "PX_PROV1",
        "full_name": "Target Person",
        "org_search_target": "Example Mobility Group",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [
            source(
                "https://profile.test/person",
                "Target Person works with Mobility on international projects.",
            )
        ],
    )
    assert decision.provisional_identity_count == 1
    assert decision.identity_resolved is False
    assert decision.final_category == "Not Classified"
    assert decision.decision_rule == "identity_only_provisionally_resolved"


def test_two_independent_provisional_identities_resolve_identity() -> None:
    row = {
        "person_id": "PX_PROV2",
        "full_name": "Target Person",
        "org_search_target": "Example Mobility Group",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [
            source(
                "https://profile-a.test/person",
                "Target Person works with Mobility on international projects.",
            ),
            source(
                "https://profile-b.test/people/target",
                "Conference biography: Target Person collaborates with Mobility "
                "on market development and research.",
            ),
        ],
    )
    assert decision.provisional_identity_count == 2
    assert decision.identity_resolved is True
    assert decision.identity_resolution_rule == (
        "two_independent_provisional_identity_sources"
    )
    assert decision.identity_source_independence_status == "INDEPENDENT"
    assert decision.final_category == "Indeterminate"


def test_two_same_domain_provisional_identities_do_not_resolve_identity() -> None:
    row = {
        "person_id": "PX_PROV3",
        "full_name": "Target Person",
        "org_search_target": "Example Mobility Group",
        "preliminary_classification": "",
    }
    decision = AdmissibilityEngine().evaluate(
        row,
        [
            source(
                "https://profiles.test/a",
                "Target Person works with Mobility on international projects.",
            ),
            source(
                "https://profiles.test/b",
                "Target Person collaborates with Mobility on market development.",
            ),
        ],
    )
    assert decision.provisional_identity_count == 2
    assert decision.identity_resolved is False
    assert decision.final_category == "Not Classified"


def test_gender_marker_elsewhere_on_page_is_not_attributed() -> None:
    row = {
        "person_id": "PX3",
        "full_name": "Alex Example",
        "org_search_target": "Example Three",
        "organisation_domain": "examplethree.org",
        "organisation_domain_status": "VERIFIED",
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


def test_flattened_contact_list_does_not_assign_english_director_to_target() -> None:
    extractor = EvidenceExtractor()
    text = (
        "Key Contacts Laurent Example Director Of Development "
        "María Target Directora De Marketing Alexandra Example"
    )
    hits = extractor.extract(text, "María Target", "https://example.test/team")
    assert [(hit.category, hit.marker) for hit in hits] == [
        ("Woman", "directora")
    ]


def test_marker_for_other_person_later_in_sentence_is_not_attributed() -> None:
    extractor = EvidenceExtractor()
    text = (
        "Target Person performed with the orchestra, conducted by Maestro Other, "
        "director titular del Teatro Ejemplo."
    )
    hits = extractor.extract(text, "Target Person", "https://example.test/news")
    assert hits == []


def test_english_president_near_byline_is_not_gender_evidence() -> None:
    extractor = EvidenceExtractor()
    text = (
        "News headline President Other attends summit Mariam Target Journalist "
        "Country PUBLISHED 26 September 2021 President Ibrahim Other concluded "
        "the official visit."
    )
    hits = extractor.extract(text, "Mariam Target", "https://example.test/news")
    assert hits == []


def test_exact_duplicate_sources_are_not_independent() -> None:
    text = "Target Person is director of Example Org."
    left = EvaluatedSource(
        source("https://a.test/x", text, sha="same"),
        "ACCEPTED",
    )
    right = EvaluatedSource(
        source("https://b.test/y", text, sha="same"),
        "ACCEPTED",
    )
    assert assess_pair(left, right).status == IndependenceStatus.EXACT_DUPLICATE.value


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
