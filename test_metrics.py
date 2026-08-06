import math

import pandas as pd

from profair_observability.config import AlgorithmConfig
from profair_observability.metrics import (
    compute_profile,
    distribution_similarity,
    log_representation_ratio,
    parity_score,
    smoothed_share,
)


def test_smoothed_share() -> None:
    assert smoothed_share(0, 0) == 0.5
    assert math.isclose(smoothed_share(5, 10), 0.5)


def test_log_ratio_and_parity() -> None:
    assert math.isclose(log_representation_ratio(0.5, 0.5), 0.0)
    under = log_representation_ratio(0.25, 0.5)
    over = log_representation_ratio(0.5, 0.25)
    assert math.isclose(under, -over)
    assert math.isclose(parity_score(under), parity_score(over))


def test_distribution_similarity() -> None:
    women = pd.Series(["A", "B", "A", "B"])
    men = pd.Series(["A", "B", "A", "B"])
    assert math.isclose(distribution_similarity(women, men), 1.0)

    separated_women = pd.Series(["A", "A"])
    separated_men = pd.Series(["B", "B"])
    assert distribution_similarity(separated_women, separated_men) == 0.0


def test_profile_composite_disabled(synthetic_frame: pd.DataFrame) -> None:
    profile = compute_profile(
        synthetic_frame,
        config=AlgorithmConfig(enable_composite=False),
    )
    assert set(profile["composite_status"]) == {"disabled_by_default"}
    assert profile["composite_parity_score"].isna().all()
