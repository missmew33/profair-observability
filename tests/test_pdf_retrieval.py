from __future__ import annotations

from pathlib import Path

import pytest

from profair_observability.admissibility import retrieval
from profair_observability.admissibility.retrieval import SourceRetriever
from profair_observability.admissibility.schema import RetrievalStatus, SearchCandidate


class FakePdfResponse:
    status_code = 200
    url = "https://official.example/document.pdf"
    headers = {
        "Content-Type": "application/pdf",
        "Content-Length": "24",
    }
    encoding = None

    def iter_content(self, chunk_size: int = 8192):
        yield b"%PDF-1.4 synthetic bytes"


def candidate() -> SearchCandidate:
    return SearchCandidate(
        query='"Target Person" "Example Org"',
        provider="test",
        rank=1,
        url="https://official.example/document.pdf",
        title="Official document",
    )


def test_pdf_with_embedded_text_is_full_text_retrieved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = SourceRetriever(cache_dir=tmp_path, per_domain_delay=0.0)
    monkeypatch.setattr(retrieval, "_host_is_public", lambda hostname: True)
    monkeypatch.setattr(
        retriever.session,
        "get",
        lambda *args, **kwargs: FakePdfResponse(),
    )
    monkeypatch.setattr(
        retrieval,
        "extract_pdf_text",
        lambda content: (
            "Target Person works for Example Org. "
            "This official document contains enough embedded text for evaluation. "
            "Additional synthetic words ensure the minimum text threshold is met."
        ),
    )

    record = retriever.fetch(candidate(), use_cache=False)

    assert record.retrieval_status == RetrievalStatus.FULL_TEXT_RETRIEVED.value
    assert record.content_type == "application/pdf"
    assert record.page_title == "Official document"
    assert "Target Person" in record.full_text


def test_pdf_without_extractable_text_remains_non_text_resource(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = SourceRetriever(cache_dir=tmp_path, per_domain_delay=0.0)
    monkeypatch.setattr(retrieval, "_host_is_public", lambda hostname: True)
    monkeypatch.setattr(
        retriever.session,
        "get",
        lambda *args, **kwargs: FakePdfResponse(),
    )
    monkeypatch.setattr(retrieval, "extract_pdf_text", lambda content: "")

    record = retriever.fetch(candidate(), use_cache=False)

    assert record.retrieval_status == RetrievalStatus.NON_TEXT_RESOURCE.value
    assert "OCR not used" in record.error_message
