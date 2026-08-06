from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon

from .config import AlgorithmConfig
from .preprocessing import canonical_relations


DIMENSION_NAMES = (
    "demographic_presence",
    "organisational_inclusion",
    "leadership_representation",
    "functional_similarity",
    "spatial_representation",
    "geographical_similarity",
)


def smoothed_share(
    successes: int | float,
    total: int | float,
    *,
    alpha: float = 0.5,
    beta: float = 0.5,
) -> float:
    """Jeffreys-smoothed binomial proportion."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Invalid successes/total.")
    return float((successes + alpha) / (total + alpha + beta))


def log_representation_ratio(observed: float, benchmark: float) -> float:
    """Signed log ratio; zero denotes equality with the benchmark."""
    if not 0 < observed < 1:
        raise ValueError("Observed proportion must lie strictly between 0 and 1.")
    if not 0 < benchmark < 1:
        raise ValueError("Benchmark must lie strictly between 0 and 1.")
    return float(np.log(observed / benchmark))


def parity_score(log_ratio: float) -> float:
    """Symmetric bounded parity score in (0, 1]."""
    return float(np.exp(-abs(log_ratio)))


def distribution_similarity(
    women: pd.Series,
    men: pd.Series,
    *,
    categories: Iterable[str] | None = None,
) -> float:
    """Normalised Jensen–Shannon similarity between category distributions."""
    if categories is None:
        categories = sorted(set(women.dropna()) | set(men.dropna()))
    categories = list(categories)
    if not categories or women.empty or men.empty:
        return float("nan")

    w = women.value_counts().reindex(categories, fill_value=0).to_numpy(float)
    m = men.value_counts().reindex(categories, fill_value=0).to_numpy(float)
    if w.sum() == 0 or m.sum() == 0:
        return float("nan")

    distance = float(jensenshannon(w / w.sum(), m / m.sum(), base=2.0))
    return float(1.0 - distance)


def _benchmark_map(
    benchmarks: pd.DataFrame | None,
    group_values: tuple[object, ...],
    config: AlgorithmConfig,
) -> dict[str, float]:
    if benchmarks is None:
        return {}

    selector = pd.Series(True, index=benchmarks.index)
    for column, value in zip(config.group_columns, group_values, strict=True):
        selector &= benchmarks[column].astype(str) == str(value)

    matches = benchmarks.loc[selector]
    if len(matches) != 1:
        return {}

    row = matches.iloc[0]
    mapping: dict[str, float] = {}
    for dimension in DIMENSION_NAMES:
        column = f"{dimension}_benchmark"
        if column in row.index and pd.notna(row[column]):
            mapping[dimension] = float(row[column])
    return mapping


def _group_profile(
    group: pd.DataFrame,
    *,
    config: AlgorithmConfig,
    benchmark_values: dict[str, float],
) -> dict[str, float | int | str]:
    classified = group[
        group["sex_gender_classification"].isin(config.classified_categories)
    ].copy()
    women = classified[classified["sex_gender_classification"] == "Woman"]
    men = classified[classified["sex_gender_classification"] == "Man"]

    n_women = len(women)
    n_men = len(men)
    n_classified = n_women + n_men

    demographic = smoothed_share(
        n_women,
        n_classified,
        alpha=config.alpha,
        beta=config.beta,
    )

    organisation_counts = (
        classified.groupby("organisation_id")["sex_gender_classification"]
        .agg(list)
    )
    eligible_organisations = len(organisation_counts)
    organisations_with_women = int(
        organisation_counts.apply(lambda values: "Woman" in values).sum()
    )
    inclusion = smoothed_share(
        organisations_with_women,
        eligible_organisations,
        alpha=config.alpha,
        beta=config.beta,
    )

    leadership = classified[
        classified["hierarchy_code"].isin(config.leadership_codes)
    ]
    leadership_women = int(
        (leadership["sex_gender_classification"] == "Woman").sum()
    )
    leadership_total = len(leadership)
    leadership_share = smoothed_share(
        leadership_women,
        leadership_total,
        alpha=config.alpha,
        beta=config.beta,
    )

    function_mask = ~classified["function_code"].fillna("").isin(
        config.function_unknown_codes
    )
    functional = classified[function_mask]
    functional_similarity = distribution_similarity(
        functional.loc[
            functional["sex_gender_classification"] == "Woman", "function_code"
        ],
        functional.loc[
            functional["sex_gender_classification"] == "Man", "function_code"
        ],
    )

    physical = classified[classified["physical_corpus_eligible"] == 1].copy()
    org_spatial = (
        physical.groupby("organisation_id", as_index=False)
        .agg(
            area=(config.area_column, "max"),
            women=(
                "sex_gender_classification",
                lambda values: int((values == "Woman").sum()),
            ),
            classified=("sex_gender_classification", "size"),
        )
    )
    org_spatial = org_spatial[
        (org_spatial["area"] > 0) & (org_spatial["classified"] > 0)
    ]
    if org_spatial.empty or float(org_spatial["area"].sum()) == 0:
        spatial = float("nan")
    else:
        org_spatial["woman_share"] = (
            org_spatial["women"] / org_spatial["classified"]
        )
        spatial = float(
            np.average(
                org_spatial["woman_share"],
                weights=org_spatial["area"],
            )
        )

    geo = classified[classified[config.geography_column].notna()]
    geographical_similarity = distribution_similarity(
        geo.loc[
            geo["sex_gender_classification"] == "Woman",
            config.geography_column,
        ],
        geo.loc[
            geo["sex_gender_classification"] == "Man",
            config.geography_column,
        ],
    )

    raw_dimensions = {
        "demographic_presence": demographic,
        "organisational_inclusion": inclusion,
        "leadership_representation": leadership_share,
        "functional_similarity": functional_similarity,
        "spatial_representation": spatial,
        "geographical_similarity": geographical_similarity,
    }

    result: dict[str, float | int | str] = {
        "person_relations": len(group),
        "classified_person_relations": n_classified,
        "women": n_women,
        "men": n_men,
        "eligible_organisations": eligible_organisations,
        "organisations_with_women": organisations_with_women,
        "leadership_relations": leadership_total,
        "leadership_women": leadership_women,
    }
    result.update(raw_dimensions)

    parity_values: dict[str, float] = {}
    for dimension, observed in raw_dimensions.items():
        benchmark = benchmark_values.get(dimension)
        if (
            benchmark is not None
            and pd.notna(observed)
            and 0 < float(observed) < 1
        ):
            log_ratio = log_representation_ratio(float(observed), benchmark)
            parity_values[dimension] = parity_score(log_ratio)
            result[f"{dimension}_benchmark"] = benchmark
            result[f"{dimension}_log_ratio"] = log_ratio
            result[f"{dimension}_parity"] = parity_values[dimension]

    result["validated_parity_dimensions"] = len(parity_values)

    if config.enable_composite:
        weighted = [
            (config.weights[dimension], value)
            for dimension, value in parity_values.items()
            if config.weights.get(dimension, 0) > 0
        ]
        if len(weighted) >= config.minimum_composite_dimensions:
            denominator = sum(weight for weight, _ in weighted)
            result["composite_parity_score"] = float(
                100.0
                * sum(weight * value for weight, value in weighted)
                / denominator
            )
            result["composite_status"] = "exploratory_enabled"
        else:
            result["composite_parity_score"] = float("nan")
            result["composite_status"] = "insufficient_validated_dimensions"
    else:
        result["composite_parity_score"] = float("nan")
        result["composite_status"] = "disabled_by_default"

    return result


def compute_profile(
    frame: pd.DataFrame,
    *,
    benchmarks: pd.DataFrame | None = None,
    config: AlgorithmConfig | None = None,
) -> pd.DataFrame:
    """Compute fair-level multidimensional observability profiles."""
    config = config or AlgorithmConfig()
    relations = canonical_relations(frame)

    rows: list[dict[str, object]] = []
    grouper: str | list[str]
    if len(config.group_columns) == 1:
        grouper = config.group_columns[0]
    else:
        grouper = list(config.group_columns)

    for keys, group in relations.groupby(grouper, dropna=False):
        key_tuple = keys if isinstance(keys, tuple) else (keys,)
        row: dict[str, object] = dict(
            zip(config.group_columns, key_tuple, strict=True)
        )
        row.update(
            _group_profile(
                group,
                config=config,
                benchmark_values=_benchmark_map(
                    benchmarks, key_tuple, config
                ),
            )
        )
        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        list(config.group_columns)
    ).reset_index(drop=True)
