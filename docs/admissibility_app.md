# ProFair Evidence-Admissibility application

Status: **pre-release audit software**. It is not yet a validated production classifier.

## Deployment model

The application has two deliberately separated modes.

### Public demo mode

Default. It accepts no direct-identifier upload and performs no live search on restricted records. Use this mode for a public Streamlit deployment and synthetic demonstrations.

### Restricted research mode

Use only in an approved local/private environment. This mode can upload names and organisations and will send search queries containing those fields to the configured search provider.

`preliminary_classification` is never used to generate queries, evidence, source types, or the Woman/Man decision. It is read only after the evidence-based decision to flag a screening conflict.

## Identity gate

Identity resolution precedes attribute evidence.

A case is treated as identity-resolved only when at least one of the following holds:

- one source reaches `ACCEPTED`; or
- two `ACCEPTED_PROVISIONAL` sources are independent under the source-independence rules.

A single provisional match, or multiple provisional matches from the same/non-independent provenance, remains `Not Classified` with `identity_only_provisionally_resolved`. This prevents weak linkage from being converted into analytical `Indeterminate` cases.

## Organisation-domain provenance

Organisation domains are explicitly separated into:

- `VERIFIED`: independently established as the organisation's official domain;
- `CANDIDATE`: plausible but not yet verified;
- `UNKNOWN`: no verified provenance status.

A supplied organisation domain can support `ORGANISATION_OFFICIAL` primary-source typing only when `organisation_domain_status=VERIFIED`. Automatically discovered high-similarity domains are surfaced as candidates and remain non-primary during pre-release validation unless the automatic-typing rule is explicitly being tested.

The restricted runner exposes discovered candidate organisation domains so they can be verified in a separate provenance step before being reused as primary official evidence.

## Search and technical failures

Search timeouts and request-layer failures are preserved as technical states. They are not converted into substantive `Not Classified` observations. Generated queries and actually executed searches are reported separately for traceability.

## Release gate

Keep automatic high-confidence official-domain typing disabled during N=150 validation. Complete the empirical audit before processing the full corpus.
