"""ProFair Observability public package."""

from .metrics import compute_profile
from .uncertainty import bootstrap_profiles, indeterminate_bounds
from .validation import validate_dataframe

__all__ = [
    "bootstrap_profiles",
    "compute_profile",
    "indeterminate_bounds",
    "validate_dataframe",
]

__version__ = "0.1.0"
