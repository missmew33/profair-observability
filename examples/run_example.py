from pathlib import Path

import pandas as pd

from profair_observability.config import AlgorithmConfig
from profair_observability.metrics import compute_profile
from profair_observability.uncertainty import indeterminate_bounds

base = Path(__file__).parent
data = pd.read_csv(base / "synthetic_exhibitors.csv")
benchmarks = pd.read_csv(base / "synthetic_benchmarks.csv")
config = AlgorithmConfig.from_yaml(base / "config.yml")

profile = compute_profile(data, benchmarks=benchmarks, config=config)
bounds = indeterminate_bounds(data, config=config)

print("Profile")
print(profile.to_string(index=False))
print("\nIndeterminate-case bounds")
print(bounds.to_string(index=False))
