from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .schema import FORBIDDEN_PUBLIC_COLUMNS, REQUIRED_COLUMNS


@dataclass(frozen=True)
class ValidationReport:
    rows: int
    columns: int
    duplicated_relations: int
    invalid_area_rows: int
    unknown_gender_categories: tuple[str, ...]


class DataValidationError(ValueError):
    """Raised when the analytical data contract is violated."""


def validate_dataframe(frame: pd.DataFrame) -> ValidationReport:
    """Validate pseudonymised person–organisation–fair input data."""
    normalised = {str(column).strip().lower() for column in frame.columns}
    forbidden = sorted(normalised.intersection(FORBIDDEN_PUBLIC_COLUMNS))
    if forbidden:
        raise DataValidationError(
            "Direct-identifier columns are prohibited in the public workflow: "
            + ", ".join(forbidden)
        )

    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise DataValidationError(
            "Missing required columns: " + ", ".join(missing)
        )

    valid_gender = {"Woman", "Man", "Indeterminate", "Not classified"}
    observed_gender = set(
        frame["sex_gender_classification"].dropna().astype(str).unique()
    )
    unknown_gender = tuple(sorted(observed_gender.difference(valid_gender)))

    area = pd.to_numeric(frame["total_area_m2"], errors="coerce")
    invalid_area = int(((area < 0) | area.isna()).sum())

    duplicated = int(
        frame.duplicated(
            subset=["fair_id", "edition_year", "organisation_id", "person_id"]
        ).sum()
    )

    if unknown_gender:
        raise DataValidationError(
            "Unknown sex/gender categories: " + ", ".join(unknown_gender)
        )
    if invalid_area:
        raise DataValidationError(
            f"{invalid_area} rows contain missing or negative exhibition area."
        )

    return ValidationReport(
        rows=len(frame),
        columns=len(frame.columns),
        duplicated_relations=duplicated,
        invalid_area_rows=invalid_area,
        unknown_gender_categories=unknown_gender,
    )
