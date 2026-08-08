from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from .engine import AdmissibilityEngine
from .provenance import build_manifest, write_jsonl
from .retrieval import SourceRetriever
from .schema import REQUIRED_INPUT_FIELDS, PersonDecision
from .search import QueryBuilder, SearchProvider, collect_candidates

PIPELINE_VERSION = "2.2.3-pre-release"


def validate_input(df: pd.DataFrame) -> None:
    missing = REQUIRED_INPUT_FIELDS - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(sorted(missing))}"
        )
    if df["person_id"].astype(str).duplicated().any():
        raise ValueError("person_id must be unique in the audit input.")


def _provider_attempts(provider: SearchProvider, start: int) -> list[dict]:
    attempts = getattr(provider, "attempts", [])
    return [dict(item) for item in attempts[start:]]


def _technical_search_failure(
    row: dict,
    attempts: list[dict],
) -> PersonDecision:
    return PersonDecision(
        person_id=str(row.get("person_id", "")),
        audit_case_id=str(row.get("audit_case_id", "") or ""),
        full_name=str(row.get("full_name", "") or "").strip(),
        org_search_target=str(row.get("org_search_target", "") or "").strip(),
        primary_fair=str(row.get("primary_fair", "") or ""),
        identity_resolved=False,
        A_i_B=0,
        final_category="",
        decision_rule="technical_search_failure_not_analytical",
        processing_status="TECHNICAL_FAILURE",
        search_attempt_count=len(attempts),
        search_error_count=len(attempts),
        search_attempts=attempts,
    )


def run_batch(
    df: pd.DataFrame,
    *,
    provider: SearchProvider,
    output_dir: str | Path,
    max_queries: int = 6,
    max_results_per_query: int = 5,
    max_urls_per_person: int = 10,
    trusted_official_domains: set[str] | None = None,
    allow_auto_official_high: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
    checkpoint_every: int = 10,
) -> tuple[pd.DataFrame, list[PersonDecision], dict]:
    validate_input(df)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)
    query_builder = QueryBuilder(max_queries=max_queries)
    retriever = SourceRetriever(cache_dir=output / "source_cache")
    engine = AdmissibilityEngine(
        allow_auto_official_high=allow_auto_official_high,
        trusted_official_domains=trusted_official_domains or set(),
    )
    decisions, flat_rows = [], []
    total = len(df)

    for position, (_, series) in enumerate(df.iterrows(), start=1):
        row = {
            k: ("" if pd.isna(v) else v)
            for k, v in series.to_dict().items()
        }
        person_id = str(row.get("person_id", ""))
        if progress:
            progress(position, total, person_id)

        queries = query_builder.build(row)
        attempt_start = len(getattr(provider, "attempts", []))
        candidates = collect_candidates(
            provider,
            queries,
            max_results_per_query=max_results_per_query,
            max_urls=max_urls_per_person,
        )
        person_attempts = _provider_attempts(provider, attempt_start)
        search_errors = [
            item for item in person_attempts if item.get("status") != "OK"
        ]
        all_attempts_failed = bool(person_attempts) and all(
            item.get("status") != "OK" for item in person_attempts
        )

        if queries and not candidates and all_attempts_failed:
            decision = _technical_search_failure(row, person_attempts)
            retrieved = []
        else:
            retrieved = retriever.fetch_many(candidates)
            decision = engine.evaluate(row, retrieved)
            decision.search_attempt_count = len(person_attempts)
            decision.search_error_count = len(search_errors)
            decision.search_attempts = person_attempts
            if search_errors:
                decision.processing_status = "PARTIAL_SEARCH_FAILURE"

        decisions.append(decision)
        flat = decision.to_flat_dict()
        flat["query_count"] = len(queries)
        flat["candidate_url_count"] = len(candidates)
        flat["retrieved_full_text_count"] = sum(
            1
            for item in retrieved
            if item.retrieval_status == "FULL_TEXT_RETRIEVED"
        )
        flat_rows.append(flat)

        if checkpoint_every > 0 and (
            position % checkpoint_every == 0 or position == total
        ):
            pd.DataFrame(flat_rows).to_csv(
                checkpoint_dir / f"checkpoint_{position:05d}.csv",
                index=False,
            )
            write_jsonl(
                decisions,
                checkpoint_dir / f"provenance_{position:05d}.jsonl",
            )

    results = pd.DataFrame(flat_rows)
    results.to_csv(output / "admissibility_results.csv", index=False)
    write_jsonl(decisions, output / "provenance.jsonl")
    manifest = build_manifest(
        input_name="in_memory_dataframe",
        input_sha256="",
        provider=provider.name,
        pipeline_version=PIPELINE_VERSION,
        case_count=total,
        settings={
            "max_queries": max_queries,
            "max_results_per_query": max_results_per_query,
            "max_urls_per_person": max_urls_per_person,
            "allow_auto_official_high": allow_auto_official_high,
            "trusted_official_domains": sorted(
                trusted_official_domains or set()
            ),
            "checkpoint_every": checkpoint_every,
        },
    )
    manifest["summary"] = {
        "n_admissible": int(results["A_i_B"].sum())
        if not results.empty
        else 0,
        "n_woman": int((results["final_category"] == "Woman").sum())
        if not results.empty
        else 0,
        "n_man": int((results["final_category"] == "Man").sum())
        if not results.empty
        else 0,
        "n_indeterminate": int(
            (results["final_category"] == "Indeterminate").sum()
        )
        if not results.empty
        else 0,
        "n_not_classified": int(
            (results["final_category"] == "Not Classified").sum()
        )
        if not results.empty
        else 0,
        "n_technical_failure": int(
            (results["processing_status"] == "TECHNICAL_FAILURE").sum()
        )
        if not results.empty
        else 0,
        "n_partial_search_failure": int(
            (
                results["processing_status"]
                == "PARTIAL_SEARCH_FAILURE"
            ).sum()
        )
        if not results.empty
        else 0,
        "search_error_count": int(results["search_error_count"].sum())
        if not results.empty
        else 0,
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results, decisions, manifest
