# Evidence admissibility

ProFair separates search, retrieval, identity resolution, evidence attribution, source qualification, and binary admissibility. Preliminary screening labels are never used as search terms or primary evidence.

## Identity gate

Identity is resolved only when there is one `ACCEPTED` identity source or two independent `ACCEPTED_PROVISIONAL` sources. Organisation context is evaluated across `org_search_target`, `account_name`, and `trade_name`; generic aliases are downgraded when a materially more specific organisational entity is available.

## Retrieval gate

Search snippets are discovery aids only. Candidate pages must be retrieved as full text before they can support identity or gender evidence. Search and retrieval failures are recorded separately from analytical `Not Classified` cases.

Embedded text in `application/pdf` resources is extracted and evaluated under the same identity and evidence rules as HTML. OCR is deliberately excluded from the automated pipeline. PDFs without sufficient embedded text remain non-text technical retrievals; no inference is made from page images or appearance.

## Gender evidence and admissibility

Binary admissibility requires attributable, linguistically unambiguous professional gender evidence from one qualifying official/institutional source or two independent concordant professional sources. Explicit alternative self-description is preserved outside the binary denominator. Names, photographs, appearance, voice, and clothing are not gender evidence.

## Organisation domains

A supplied organisation domain is eligible for primary official status only when `organisation_domain_status=VERIFIED`. Automatically discovered or inferred domains remain `CANDIDATE`/`UNKNOWN` until independently verified.

## Pre-release status

The evidence-admissibility layer remains pre-release audit software. Full-corpus use is blocked until the empirical N=150 audit and release-gate precision criteria are completed.
