# Data governance

## Public layer

May contain code, documentation, synthetic data, schemas, aggregate outputs
passing disclosure review, and tests.

## Restricted layer

Must remain outside GitHub:

- names;
- emails;
- telephone numbers;
- addresses;
- raw source files;
- restricted linkage keys;
- manually reviewed evidence containing identifiable information.

## Analytical layer

The software expects pseudonymous identifiers and derived classifications.
Direct identifiers are neither required nor accepted by the default
validation command.

## Disclosure review

Before publishing aggregate results:

1. inspect small cells;
2. suppress or combine disclosure-risking categories;
3. avoid rare combinations that permit re-identification;
4. document the disclosure-control decision.
