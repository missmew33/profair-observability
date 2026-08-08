# Validation protocol

The algorithm must be validated before a composite score is treated as a
substantive contribution.

## 1. Measurement validation

- validate person and organisation linkage;
- audit the identity gate separately for `ACCEPTED`, paired independent
  `ACCEPTED_PROVISIONAL`, and unresolved cases;
- estimate identity-resolution precision and attribution precision with
  confidence intervals;
- verify organisation-domain provenance separately from source-content
  classification, distinguishing `VERIFIED`, `CANDIDATE`, and `UNKNOWN`;
- estimate gender-classification error overall, by fair, continent, and name
  structure;
- assess inter-coder reliability for function and hierarchy;
- validate exhibition area against commercial or company-size information
  where available.

A single `ACCEPTED_PROVISIONAL` identity match must not be treated as resolved.
Identity resolution requires either one `ACCEPTED` source or two independent
`ACCEPTED_PROVISIONAL` sources.

A discovered or supplied organisation domain must not be treated as primary
official evidence unless its provenance status is `VERIFIED`. Candidate-domain
discovery and domain verification are separate operations.

## 2. Content validity

An expert panel should assess whether each dimension adequately represents
the theoretical construct of market observability.

## 3. Construct validity

Evaluate whether the dimensions distinguish:

- demographic presence from organisational inclusion;
- presence from leadership;
- numerical presence from functional distribution;
- unweighted presence from area-weighted visibility.

## 4. Convergent and external validity

Compare profile dimensions with:

- sectoral employment benchmarks;
- leadership benchmarks;
- validated organisation-level company data;
- earlier longitudinal FITUR results.

## 5. Known-groups validity

Test whether the method distinguishes theoretically expected configurations,
while treating those tests as validation evidence rather than proof.

## 6. Reliability and uncertainty

- organisation-cluster bootstrap;
- one-person-per-organisation resampling;
- lower and upper bounds for indeterminate cases;
- narrow and broad leadership definitions;
- alternative weight sets;
- leave-one-fair-out analysis.

## 7. Measurement invariance

Assess whether classification and metric behaviour differ by fair, continent,
language structure, and registration intensity.

## 8. Evidence-admissibility release audit

Before full-corpus evidence-admissibility processing:

- audit a stratified N=150 sample with preserved provenance;
- report identity-resolution precision, evidence-attribution precision, and
  binary-admissibility precision with Wilson confidence intervals;
- treat pre-specified point-estimate criteria of 99%, 99%, and 98%,
  respectively, as software release criteria rather than theoretical truths;
- keep technical failures outside `Not Classified` and rerun them separately;
- keep automatic high-confidence official-domain typing disabled unless that
  rule is itself under explicit validation.

## 9. Release criterion

The composite index remains exploratory until:

- all primary dimensions have defensible operational definitions;
- classification error is quantified;
- no single dimension dominates under reasonable scaling;
- weight sensitivity is reported;
- external and construct validation are documented;
- the algorithm version is frozen before final substantive interpretation.
