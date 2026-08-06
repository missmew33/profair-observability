# Contributing

1. Create a branch from `main`.
2. Add or update tests for every analytical change.
3. Run `ruff check .` and `pytest`.
4. Use synthetic data only.
5. Document changes to equations, defaults, thresholds, or weights.
6. Changes affecting substantive meaning require a methodological rationale,
   a versioned change-log entry, new validation evidence, and updated
   documentation.

Composite weights must not be changed merely because they improve a result.
