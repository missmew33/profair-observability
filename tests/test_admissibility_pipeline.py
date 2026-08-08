from __future__ import annotations

import hashlib

import pytest

from profair_observability.admissibility.engine import AdmissibilityEngine
from profair_observability.admissibility.independence import assess_pair
from profair_observability.admissibility.identity import IdentityResolver
from profair_observability.admissibility.privacy import enforce_public_mode
from profair_observability.admissibility.schema import EvaluatedSource, IndependenceStatus, RetrievedSource, RetrievalStatus
from profair_observability.admissibility.search import QueryBuilder


def source(url: str, text: str, sha: str | None = None) -> RetrievedSource:
    return RetrievedSource(query='"Target Person" "Example Org"', provider="test", rank=1, requested_url=url, final_url=url, retrieval_status=RetrievalStatus.FULL_TEXT_RETRIEVED.value, full_text=text, page_title="Example Org", content_sha256=sha or hashlib.sha256(text.encode()).hexdigest())


def test_queries_never_use_preliminary_classification() -> None:
    row = {"full_name": "María Example", "org_search_target": "Example Org", "country_code": "ES", "preliminary_classification": "Woman"}
    queries = QueryBuilder().build(row)
    assert queries
    assert all("Woman" not in q for q in queries)


def test_identity_requires_nearby_organisation_context() -> None:
    resolver = IdentityResolver(window_chars=120)
    text = "Target Person presented the project. " + ("x " * 200) + "Example Org sponsors the event."
    match = resolver.evaluate(text, "Target Person", "Example Org")
    assert match.status == "REJECTED_NO_COOCCURRENCE"


def test_official_direct_gendered_evidence_is_admissible() -> None:
    row = {"person_id": "PX1", "full_name": "Ana Ejemplo", "org_search_target": "Ejemplo Uno", "organisation_domain": "ejemplouno.org", "preliminary_classification": ""}
    decision = AdmissibilityEngine().evaluate(row, [source("https://ejemplouno.org/equipo", "Ana Ejemplo es directora de innovación de Ejemplo Uno.")])
    assert decision.A_i_B == 1
    assert decision.final_category == "Woman"


def test_single_secondary_source_is_not_admissible() -> None:
    row = {"person_id": "PX2", "full_name": "Luis Ejemplo", "org_search_target": "Ejemplo Dos", "preliminary_classification": ""}
    decision = AdmissibilityEngine().evaluate(row, [source("https://industrynews.test/interview", "Luis Ejemplo es director comercial de Ejemplo Dos.")])
    assert decision.A_i_B == 0
    assert decision.final_category == "Indeterminate"


def test_gender_marker_elsewhere_on_page_is_not_attributed() -> None:
    row = {"person_id": "PX3", "full_name": "Alex Example", "org_search_target": "Example Three", "organisation_domain": "examplethree.org", "preliminary_classification": ""}
    text = "Alex Example works at Example Three on market development. A separate biography appears here. Maria Other is directora of another unit."
    decision = AdmissibilityEngine().evaluate(row, [source("https://examplethree.org/team", text)])
    assert decision.A_i_B == 0
    assert decision.final_category == "Indeterminate"


def test_exact_duplicate_sources_are_not_independent() -> None:
    text = "Target Person is director of Example Org."
    a = EvaluatedSource(source("https://a.test/x", text, sha="same"), "ACCEPTED")
    b = EvaluatedSource(source("https://b.test/y", text, sha="same"), "ACCEPTED")
    assert assess_pair(a, b).status == IndependenceStatus.EXACT_DUPLICATE.value


def test_public_mode_rejects_direct_identifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROFAIR_RESTRICTED_MODE", raising=False)
    with pytest.raises(ValueError):
        enforce_public_mode(["person_id", "full_name", "primary_fair"])
