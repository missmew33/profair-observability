from __future__ import annotations

import re
from urllib.parse import urlparse

from rapidfuzz.fuzz import ratio
from unidecode import unidecode

from .domains import domain_label, registrable_domain
from .schema import OrganisationDomainStatus, RetrievedSource, SourceType

PUBLIC_INSTITUTION_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".gob.es",
    ".gob.mx",
    ".gob.ar",
    ".gouv.fr",
    ".bund.de",
    ".edu",
    ".ac.uk",
)
PROFESSIONAL_NETWORK_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "es.linkedin.com",
    "fr.linkedin.com",
    "it.linkedin.com",
    "de.linkedin.com",
}


def _norm(value: str) -> str:
    value = unidecode(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _domain_org_similarity(url: str, org_target: str) -> float:
    label = _norm(domain_label(url)).replace(" ", "")
    org = _norm(org_target).replace(" ", "")
    return ratio(label, org) / 100.0 if label and org else 0.0


def _clean_domain(value: str) -> str:
    return (
        (value or "")
        .strip()
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .split("/")[0]
    )


def _domain_status(value: str) -> str:
    normalized = (value or "").strip().upper()
    allowed = {item.value for item in OrganisationDomainStatus}
    return (
        normalized
        if normalized in allowed
        else OrganisationDomainStatus.UNKNOWN.value
    )


def classify_source(
    source: RetrievedSource,
    org_target: str,
    organisation_domain: str = "",
    organisation_domain_status: str = OrganisationDomainStatus.UNKNOWN.value,
    trusted_official_domains: set[str] | None = None,
) -> RetrievedSource:
    trusted_official_domains = {
        d.lower() for d in (trusted_official_domains or set())
    }
    url = source.final_url or source.requested_url
    host = (urlparse(url).hostname or "").lower()
    registrable = registrable_domain(url)

    if host in PROFESSIONAL_NETWORK_HOSTS or registrable == "linkedin.com":
        source.source_type = SourceType.PROFESSIONAL_NETWORK.value
        source.source_type_confidence = 0.99
        source.source_type_reason = "Known professional-network domain."
        return source

    supplied = _clean_domain(organisation_domain)
    supplied_status = _domain_status(organisation_domain_status)
    supplied_match = bool(
        supplied
        and (
            host == supplied
            or host.endswith("." + supplied)
            or registrable == supplied
        )
    )
    if supplied_match and supplied_status == OrganisationDomainStatus.VERIFIED.value:
        source.source_type = SourceType.ORGANISATION_OFFICIAL.value
        source.source_type_confidence = 0.99
        source.source_type_reason = (
            "Matches organisation_domain with VERIFIED provenance status."
        )
        return source
    if supplied_match:
        source.source_type = SourceType.OFFICIAL_CANDIDATE.value
        source.source_type_confidence = 0.99
        source.source_type_reason = (
            "Matches supplied organisation_domain, but domain status is not VERIFIED."
        )
        return source

    if host in trusted_official_domains or registrable in trusted_official_domains:
        source.source_type = SourceType.INSTITUTIONAL_OFFICIAL.value
        source.source_type_confidence = 0.99
        source.source_type_reason = (
            "Matches explicit trusted-official-domain allowlist."
        )
        return source

    if any(host.endswith(suffix) for suffix in PUBLIC_INSTITUTION_SUFFIXES):
        source.source_type = SourceType.INSTITUTIONAL_OFFICIAL.value
        source.source_type_confidence = 0.95
        source.source_type_reason = "Public/academic institutional hostname suffix."
        return source

    similarity = _domain_org_similarity(url, org_target)
    page_blob = _norm(f"{source.page_title} {source.full_text[:1000]}")
    org_norm = _norm(org_target)
    org_present = bool(org_norm and org_norm in page_blob)
    if similarity >= 0.88 and org_present:
        source.source_type = SourceType.OFFICIAL_AUTO_HIGH.value
        source.source_type_confidence = round(similarity, 3)
        source.source_type_reason = (
            "Very high domain–organisation similarity plus organisation text match; "
            "candidate only unless automatic typing is explicitly enabled."
        )
        return source
    if similarity >= 0.60 and org_present:
        source.source_type = SourceType.OFFICIAL_CANDIDATE.value
        source.source_type_confidence = round(similarity, 3)
        source.source_type_reason = (
            "Moderate domain–organisation similarity; not automatically primary."
        )
        return source

    source.source_type = SourceType.PROFESSIONAL_SECONDARY.value
    source.source_type_confidence = 0.5
    source.source_type_reason = "No strong official-domain relation established."
    return source
