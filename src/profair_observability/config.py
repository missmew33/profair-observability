from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AlgorithmConfig:
    """Configuration for the observability profile."""

    group_columns: tuple[str, ...] = ("fair_id", "edition_year")
    leadership_codes: tuple[str, ...] = ("H1",)
    broad_leadership_codes: tuple[str, ...] = ("H1", "H2")
    classified_categories: tuple[str, ...] = ("Woman", "Man")
    function_unknown_codes: tuple[str, ...] = ("unknown", "indeterminate", "")
    geography_column: str = "continent"
    area_column: str = "total_area_m2"
    alpha: float = 0.5
    beta: float = 0.5
    enable_composite: bool = False
    minimum_composite_dimensions: int = 4
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "demographic_presence": 1.0,
            "organisational_inclusion": 1.0,
            "leadership_representation": 1.0,
            "functional_similarity": 1.0,
            "spatial_representation": 1.0,
            "geographical_similarity": 1.0,
        }
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> AlgorithmConfig:
        with Path(path).open(encoding="utf-8") as handle:
            raw: dict[str, Any] = yaml.safe_load(handle) or {}

        tuple_fields = (
            "group_columns",
            "leadership_codes",
            "broad_leadership_codes",
            "classified_categories",
            "function_unknown_codes",
        )
        for field_name in tuple_fields:
            if field_name in raw:
                raw[field_name] = tuple(raw[field_name])
        return cls(**raw)
