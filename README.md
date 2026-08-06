# ProFair Observability

**ProFair Observability** is an open and reproducible computational framework
for measuring how trade fairs render sectoral markets selectively observable
through organisations and registered person–organisation–fair relations.

The package implements the methodological contribution developed in the
doctoral dissertation:

> *Trade Fairs as Infrastructures of Gendered Market Representation:
> Selective Articulation, Positional Delegation, and Gendered Market
> Observability.*

## Status

Version `0.1.0` is a research prototype. It implements the data contract,
multidimensional observability profile, uncertainty procedures, sensitivity
bounds, synthetic demonstration data, and automated tests.

The composite index is **disabled by default**. The primary output is a
multidimensional profile. A composite score may be calculated only when a
benchmark and explicit weights have been supplied and the validation
requirements have been met.

## Core analytical idea

The framework distinguishes:

1. the underlying sectoral population;
2. organisations selected into the fair;
3. persons administratively associated with those organisations;
4. attributes recorded by the fair infrastructure; and
5. analytical entities reconstructed and validated by the researcher.

The algorithm does not claim that an administrative contact is necessarily a
verified physical attendee or publicly visible representative.

## Dimensions

- demographic presence;
- organisational inclusion;
- leadership representation;
- functional-distribution similarity;
- area-weighted spatial representation;
- geographical-distribution similarity.

Benchmark-adjusted dimensions are reported through a signed log
representation ratio and a bounded parity score.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Synthetic example

```bash
profair validate-data examples/synthetic_exhibitors.csv

profair profile \
  examples/synthetic_exhibitors.csv \
  --benchmarks examples/synthetic_benchmarks.csv \
  --config examples/config.yml \
  --output outputs/profile.csv
```

The command writes a local generated result to `outputs/profile.csv`. A
version-controlled expected synthetic result is stored in
`examples/expected_profile.csv` for reproducibility and regression checks.
Files generated under `outputs/` remain local and are ignored by Git.

## Data protection

This public repository must never contain raw IFEMA MADRID data, names,
emails, telephone numbers, postal addresses, access credentials, or any
restricted linkage key.

Only code, schemas, synthetic data, disclosure-controlled aggregate outputs,
documentation, and tests may be committed.

The CLI rejects common direct-identifier column names by default.

## Repository structure

```text
profair-observability/
├── src/profair_observability/   Python package
├── tests/                       Automated tests
├── examples/                    Synthetic inputs and expected reference output
├── docs/                        Theory, equations and validation protocol
├── data/                        Data-governance notice only
├── outputs/                     Generated local outputs, ignored by Git
├── .github/workflows/           Continuous integration
├── CITATION.cff                 Citation metadata
├── pyproject.toml               Package and tool configuration
└── README.md
```

## Citation

Use `CITATION.cff`. Add the archived-release DOI after the first public
release.

## Licence

Code is released under the MIT Licence. This may be changed before the first
public release if institutional agreements require another model.
