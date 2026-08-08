# ProFair Evidence-Admissibility application

Status: **pre-release audit software**. It is not yet a validated production classifier.

## Deployment model

The application has two deliberately separated modes.

### Public demo mode

Default. It accepts no direct-identifier upload and performs no live search on restricted records. Use this mode for a public Streamlit deployment and synthetic demonstrations.

### Restricted research mode

Use only in an approved local/private environment. This mode can upload names and organisations and will send search queries containing those fields to the configured search provider.

`preliminary_classification` is never used to generate queries, evidence, source types, or the Woman/Man decision. It is read only after the evidence-based decision to flag a screening conflict.

## Release gate

Keep automatic high-confidence official-domain typing disabled during N=150 validation. Complete the empirical audit before processing the full corpus.
