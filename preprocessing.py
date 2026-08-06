from __future__ import annotations

import pandas as pd

from .validation import validate_dataframe


def canonical_relations(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one pseudonymous person–organisation–fair relation per row."""
    validate_dataframe(frame)
    result = frame.copy()
    result["total_area_m2"] = pd.to_numeric(
        result["total_area_m2"], errors="raise"
    )
    result["physical_corpus_eligible"] = (
        pd.to_numeric(result["physical_corpus_eligible"], errors="raise")
        .astype(int)
    )
    result = result.sort_values(
        ["fair_id", "edition_year", "organisation_id", "person_id"]
    )
    result = result.drop_duplicates(
        subset=["fair_id", "edition_year", "organisation_id", "person_id"],
        keep="first",
    )
    return result.reset_index(drop=True)
