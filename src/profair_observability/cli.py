from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import AlgorithmConfig
from .metrics import compute_profile
from .uncertainty import bootstrap_profiles, indeterminate_bounds
from .validation import validate_dataframe


def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def _config(path: str | None) -> AlgorithmConfig:
    return AlgorithmConfig.from_yaml(path) if path else AlgorithmConfig()


def _benchmarks(path: str | None) -> pd.DataFrame | None:
    return _read_csv(path) if path else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="profair")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-data")
    validate.add_argument("input")

    profile = subparsers.add_parser("profile")
    profile.add_argument("input")
    profile.add_argument("--benchmarks")
    profile.add_argument("--config")
    profile.add_argument("--output", required=True)

    bounds = subparsers.add_parser("bounds")
    bounds.add_argument("input")
    bounds.add_argument("--config")
    bounds.add_argument("--output", required=True)

    bootstrap = subparsers.add_parser("bootstrap")
    bootstrap.add_argument("input")
    bootstrap.add_argument("--benchmarks")
    bootstrap.add_argument("--config")
    bootstrap.add_argument("--iterations", type=int, default=1000)
    bootstrap.add_argument("--seed", type=int, default=20260731)
    bootstrap.add_argument("--output", required=True)

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "validate-data":
        report = validate_dataframe(_read_csv(args.input))
        print(report)
        return

    frame = _read_csv(args.input)
    config = _config(getattr(args, "config", None))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.command == "profile":
        result = compute_profile(
            frame,
            benchmarks=_benchmarks(args.benchmarks),
            config=config,
        )
    elif args.command == "bounds":
        result = indeterminate_bounds(frame, config=config)
    elif args.command == "bootstrap":
        result = bootstrap_profiles(
            frame,
            benchmarks=_benchmarks(args.benchmarks),
            config=config,
            iterations=args.iterations,
            seed=args.seed,
        )
    else:
        raise RuntimeError(f"Unsupported command: {args.command}")

    result.to_csv(output, index=False)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
