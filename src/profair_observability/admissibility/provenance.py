from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from collections.abc import Iterable
from pathlib import Path

from .schema import PersonDecision


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(decisions: Iterable[PersonDecision], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision.to_provenance_dict(), ensure_ascii=False) + "\n")


def build_manifest(*, input_name: str, input_sha256: str, provider: str, pipeline_version: str, case_count: int, settings: dict) -> dict:
    return {
        "pipeline": "ProFair Evidence-Admissibility",
        "pipeline_version": pipeline_version,
        "status": "PRE_RELEASE_AUDIT",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "input": {"name": input_name, "sha256": input_sha256, "case_count": case_count},
        "search_provider": provider,
        "settings": settings,
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "methodological_guards": {
            "preliminary_classification_used_only_after_decision": True,
            "appearance_based_inference": False,
            "name_based_gender_inference": False,
            "identity_and_gender_evidence_separate": True,
            "search_snippets_are_primary_evidence": False,
        },
    }
