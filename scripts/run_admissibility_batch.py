from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from profair_observability.admissibility.batch import run_batch
from profair_observability.admissibility.privacy import enforce_public_mode
from profair_observability.admissibility.search import BraveSearchProvider, SerpAPISearchProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ProFair evidence-admissibility audit batch.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("audit_output"))
    parser.add_argument("--provider", choices=["serpapi", "brave"], default="serpapi")
    parser.add_argument("--limit", type=int, default=0, help="0 means all input rows")
    parser.add_argument("--max-queries", type=int, default=5)
    parser.add_argument("--max-urls", type=int, default=8)
    parser.add_argument("--trusted-domain", action="append", default=[])
    parser.add_argument("--allow-auto-official-high", action="store_true", help="Pre-release testing only; keep off for N=150 validation unless explicitly audited.")
    args = parser.parse_args()
    df = pd.read_csv(args.input_csv)
    enforce_public_mode(df.columns)
    if args.limit > 0:
        df = df.head(args.limit).copy()
    provider = SerpAPISearchProvider() if args.provider == "serpapi" else BraveSearchProvider()
    run_batch(df, provider=provider, output_dir=args.output, max_queries=args.max_queries, max_urls_per_person=args.max_urls, trusted_official_domains={d.lower() for d in args.trusted_domain}, allow_auto_official_high=args.allow_auto_official_high)
    print(f"Completed. Outputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
