from __future__ import annotations

import re
from urllib.parse import urlparse

from rapidfuzz.fuzz import ratio
from unidecode import unidecode

from .domains import domain_label, registrable_domain
from .schema import RetrievedSource, SourceType

PUBLIC_INSTITUTION_SUFFIXES = (".gov", ".gov.uk", ".gob.es", ".gob.mx", ".gob.ar", ".gouv.fr", ".bund.de", ".edu", ".ac.uk")
PROFESSIONAL_NETWORK_HOSTS = {"linkedin.com", "www.linkedin.com", "es.linkedin.com", "fr.linkedin.com", "it.linkedin.com", "de.linkedin.com"}


def _norm(value: str) -> str:
    value = unidecode(value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _domain_org_similarity(url: str, org_target: str) -> float:
    label = _norm(domain_label(url)).replace(" ", "")
    org = _norm(org_target).replace(" ", "")
    return ratio(label, org) / 100.0 if label and org else 0.0


def classify_source(source: RetrievedSource, org_target: str, organisation_domain: str = "", trusted_official_domains: set[str] | None = None) -> RetrievedSource:
    trusted_official_domains = {d.lower() for d in (trusted_official_domains or set())}
    url = source.final_url or source.requested_url
    host = (urlparse(url).hostname or "").lower()
    registrable = registrable_domain(url)
    if host in PROFESSIONAL_NETWORK_HOSTS or registrable == "linkedin.com":
        source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.PROFESSIONAL_NETWORK.value, 0.99, "Known professional-network domain."
        return source
    supplied = organisation_domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if supplied and (host == supplied or host.endswith("." + supplied) or registrable == supplied):
        source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.ORGANISATION_OFFICIAL.value, 0.99, "Matches user-supplied organisation_domain."
        return source
    if host in trusted_official_domains or registrable in trusted_official_domains:
        source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.INSTITUTIONAL_OFFICIAL.value, 0.99, "Matches explicit trusted-official-domain allowlist."
        return source
    if any(host.endswith(suffix) for suffix in PUBLIC_INSTITUTION_SUFFIXES):
        source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.INSTITUTIONAL_OFFICIAL.value, 0.95, "Public/academic institutional hostname suffix."
        return source
    similarity = _domain_org_similarity(url, org_target)
    page_blob = _norm(f"{source.page_title} {source.full_text[:1000]}")
    org_norm = _norm(org_target)
    org_present = bool(org_norm and org_norm in page_blob)
    if similarity >= 0.88 and org_present:
        source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.OFFICIAL_AUTO_HIGH.value, round(similarity, 3), "Very high domain–organisation similarity plus organisation text match."
        return source
    if similarity >= 0.60 and org_present:
        source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.OFFICIAL_CANDIDATE.value, round(similarity, 3), "Moderate domain–organisation similarity; not automatically primary."
        return source
    source.source_type, source.source_type_confidence, source.source_type_reason = SourceType.PROFESSIONAL_SECONDARY.value, 0.5, "No strong official-domain relation established."
    return source
