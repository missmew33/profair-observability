from __future__ import annotations

import numpy as np
import pandas as pd

from .config import AlgorithmConfig
from .metrics import DIMENSION_NAMES, compute_profile
from .preprocessing import canonical_relations


def indeterminate_bounds(
    frame: pd.DataFrame,
    *,
    config: AlgorithmConfig | None = None,
) -> pd.DataFrame:
    """Bounds assigning all indeterminate cases to each binary category."""
    config = config or AlgorithmConfig()
    relations = canonical_relations(frame)

    lower = relations.copy()
    lower.loc[
        lower["sex_gender_classification"].isin(
            ["Indeterminate", "Not classified"]
        ),
        "sex_gender_classification",
    ] = "Man"

    upper = relations.copy()
    upper.loc[
        upper["sex_gender_classification"].isin(
            ["Indeterminate", "Not classified"]
        ),
        "sex_gender_classification",
    ] = "Woman"

    lower_profile = compute_profile(lower, config=config)
    upper_profile = compute_profile(upper, config=config)

    keys = list(config.group_columns)
    result = lower_profile[keys].copy()
    for dimension in (
        "demographic_presence",
        "organisational_inclusion",
        "leadership_representation",
        "spatial_representation",
    ):
        result[f"{dimension}_lower"] = lower_profile[dimension]
        result[f"{dimension}_upper"] = upper_profile[dimension]
    return result


def _resample_organisations(
    group: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    organisations = group["organisation_id"].drop_duplicates().to_numpy()
    sampled = rng.choice(organisations, size=len(organisations), replace=True)
    pieces: list[pd.DataFrame] = []
    for draw_index, organisation in enumerate(sampled):
        piece = group[group["organisation_id"] == organisation].copy()
        piece["organisation_id"] = (
            piece["organisation_id"].astype(str)
            + f"__bootstrap_{draw_index}"
        )
        pieces.append(piece)
    return pd.concat(pieces, ignore_index=True)


def bootstrap_profiles(
    frame: pd.DataFrame,
    *,
    benchmarks: pd.DataFrame | None = None,
    config: AlgorithmConfig | None = None,
    iterations: int = 1000,
    seed: int = 20260731,
) -> pd.DataFrame:
    """Organisation-cluster bootstrap percentile intervals."""
    if iterations < 20:
        raise ValueError("At least 20 bootstrap iterations are required.")

    config = config or AlgorithmConfig()
    relations = canonical_relations(frame)
    rng = np.random.default_rng(seed)
    draws: list[pd.DataFrame] = []

    grouper: str | list[str]
    if len(config.group_columns) == 1:
        grouper = config.group_columns[0]
    else:
        grouper = list(config.group_columns)

    grouped = list(relations.groupby(grouper, dropna=False))

    for iteration in range(iterations):
        sampled_groups: list[pd.DataFrame] = []
        for _, group in grouped:
            sampled_groups.append(_resample_organisations(group, rng))
        sampled_frame = pd.concat(sampled_groups, ignore_index=True)
        profile = compute_profile(
            sampled_frame,
            benchmarks=benchmarks,
            config=config,
        )
        profile["iteration"] = iteration
        draws.append(profile)

    all_draws = pd.concat(draws, ignore_index=True)
    dimensions = [
        dimension
        for dimension in DIMENSION_NAMES
        if dimension in all_draws.columns
    ]
    if "composite_parity_score" in all_draws.columns:
        dimensions.append("composite_parity_score")

    rows: list[dict[str, object]] = []
    for keys, group in all_draws.groupby(
        list(config.group_columns), dropna=False
    ):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        row: dict[str, object] = dict(
            zip(config.group_columns, key_tuple, strict=True)
        )
        for dimension in dimensions:
            values = group[dimension].dropna().to_numpy(float)
            if values.size:
                row[f"{dimension}_median"] = float(np.median(values))
                row[f"{dimension}_lower_95"] = float(
                    np.quantile(values, 0.025)
                )
                row[f"{dimension}_upper_95"] = float(
                    np.quantile(values, 0.975)
                )
        rows.append(row)

    return pd.DataFrame(rows)
