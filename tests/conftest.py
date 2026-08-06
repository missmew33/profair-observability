from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture()
def synthetic_frame() -> pd.DataFrame:
    path = Path(__file__).parents[1] / "examples" / "synthetic_exhibitors.csv"
    return pd.read_csv(path)
