from __future__ import annotations

from urllib.parse import urlparse

COMMON_TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au",
    "com.br", "com.mx", "com.ar", "com.tr", "com.cn",
    "co.jp", "co.kr", "com.sg", "com.hk", "co.nz",
}


def hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower().strip(".")


def registrable_domain(url: str) -> str:
    host = hostname(url)
    if not host:
        return ""
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    suffix2 = ".".join(labels[-2:])
    if suffix2 in COMMON_TWO_LEVEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def domain_label(url: str) -> str:
    reg = registrable_domain(url)
    if not reg:
        return ""
    parts = reg.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in COMMON_TWO_LEVEL_SUFFIXES:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else parts[0]
