import pytest

from profair_observability.validation import (
    DataValidationError,
    validate_dataframe,
)


def test_valid_frame(synthetic_frame) -> None:
    report = validate_dataframe(synthetic_frame)
    assert report.rows == len(synthetic_frame)
    assert report.invalid_area_rows == 0


def test_direct_identifier_rejected(synthetic_frame) -> None:
    frame = synthetic_frame.copy()
    frame["email"] = "prohibited@example.org"
    with pytest.raises(DataValidationError):
        validate_dataframe(frame)
