from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable

import requests
from requests.adapters import HTTPAdapter
from unidecode import unidecode
from urllib3.util.retry import Retry

from .schema import SearchCandidate


LEGAL_OR_GENERIC_SUFFIXES = {
    "sa",
    "sl",
    "srl",
    "spa",
    "ltd",
    "limited",
    "inc",
    "llc",
    "gmbh",
    "group",
    "company",
    "corporation",
    "corp",
}
ARTICLE_STOPWORDS = {
    "the",
    "and",
    "of",
    "de",
    "del",
    "la",
    "las",
    "los",
    "el",
    "da",
    "do",
    "di",
}


def _clean(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def _norm_org(value: object) -> str:
    text = unidecode(_clean(value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _informative_org_tokens(value: object) -> list[str]:
    return [
        token
        for token in _norm_org(value).split()
        if token not in ARTICLE_STOPWORDS and token not in LEGAL_OR_GENERIC_SUFFIXES
    ]


def organisation_aliases(row: dict) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    for key in ("org_search_target", "account_name", "trade_name"):
        value = _clean(row.get(key, ""))
        norm = _norm_org(value)
        if value and norm and norm not in seen:
            seen.add(norm)
            aliases.append(value)
    return aliases


def weak_identity_aliases(row: dict) -> set[str]:
    """Return aliases too generic to make an exact text match strong by itself.

    A short trade/destination label is treated as weak when it is fully
    contained in a materially more specific account/legal entity. Legal-only
    suffixes such as Ltd/SL/Corporation do not make the longer form stronger.
    """
    target = _clean(row.get("org_search_target", ""))
    account = _clean(row.get("account_name", ""))
    if not target or not account:
        return set()

    target_tokens = set(_informative_org_tokens(target))
    account_tokens = set(_informative_org_tokens(account))
    if not target_tokens or not account_tokens:
        return set()

    additional = account_tokens - target_tokens
    if (
        target_tokens < account_tokens
        and len(target_tokens) <= 2
        and len(additional) >= 2
    ):
        return {_norm_org(target)}
    return set()


def organisation_target(row: dict) -> str:
    aliases = organisation_aliases(row)
    return aliases[0] if aliases else ""


def name_variants(full_name: str) -> list[str]:
    name = re.sub(r"\s+", " ", _clean(full_name))
    if not name:
        return []
    variants = [name]
    ascii_name = unidecode(name)
    if ascii_name.lower() != name.lower():
        variants.append(ascii_name)
    parts = name.split()
    if len(parts) >= 3:
        variants.append(f"{parts[0]} {' '.join(parts[-2:])}")
        variants.append(f"{parts[0][0]}. {' '.join(parts[1:])}")
    if len(parts) == 2:
        variants.append(f"{parts[1]} {parts[0]}")
    out, seen = [], set()
    for item in variants:
        key = item.casefold()
        if len(item) >= 4 and key not in seen:
            seen.add(key)
            out.append(item)
    return out


class QueryBuilder:
    def __init__(self, max_queries: int = 6) -> None:
        self.max_queries = max_queries

    def build(self, row: dict) -> list[str]:
        full_name = _clean(row.get("full_name", ""))
        country = _clean(row.get("country_code", ""))
        if not full_name:
            return []

        names = name_variants(full_name)
        aliases = organisation_aliases(row)
        queries: list[str] = []

        # Search distinct organisation representations before looser fallbacks.
        if aliases:
            for alias in aliases:
                queries.append(f'"{names[0]}" "{alias}"')
            queries.append(f'"{names[0]}" {aliases[0]}')
        else:
            queries.append(f'"{names[0]}"')

        for name in names[1:]:
            if aliases:
                queries.append(f'"{name}" "{aliases[0]}"')
            else:
                queries.append(f'"{name}"')

        if country and aliases:
            queries.append(f'"{names[0]}" "{aliases[0]}" {country}')

        unique, seen = [], set()
        for query in queries:
            key = query.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(query)
        return unique[: self.max_queries]


def create_robust_session(
    retries: int = 2,
    backoff_factor: float = 1.5,
) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class SearchProvider(ABC):
    name: str

    def __init__(self, min_interval_seconds: float = 0.5) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0
        self.attempts: list[dict] = []

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _record_attempt(
        self,
        *,
        query: str,
        status: str,
        result_count: int = 0,
        error: str = "",
    ) -> None:
        self.attempts.append(
            {
                "query": query,
                "provider": self.name,
                "status": status,
                "result_count": result_count,
                "error": error,
            }
        )

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchCandidate]:
        raise NotImplementedError


class SerpAPISearchProvider(SearchProvider):
    name = "serpapi"

    def __init__(
        self,
        api_key: str | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        retries: int = 2,
        backoff_factor: float = 1.5,
        min_interval_seconds: float = 0.5,
    ) -> None:
        super().__init__(min_interval_seconds=min_interval_seconds)
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        self.timeout = (connect_timeout, read_timeout)
        self.session = create_robust_session(
            retries=retries,
            backoff_factor=backoff_factor,
        )
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is required for SerpAPI search.")

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchCandidate]:
        self._wait_for_rate_limit()
        try:
            response = self.session.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google",
                    "q": query,
                    "api_key": self.api_key,
                    "num": max_results,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            self._record_attempt(query=query, status="TIMEOUT", error=str(exc))
            return []
        except requests.RequestException as exc:
            self._record_attempt(query=query, status="REQUEST_ERROR", error=str(exc))
            return []
        except ValueError as exc:
            self._record_attempt(query=query, status="INVALID_JSON", error=str(exc))
            return []

        candidates = []
        for rank, item in enumerate(
            payload.get("organic_results", [])[:max_results],
            start=1,
        ):
            url = item.get("link", "")
            if url:
                candidates.append(
                    SearchCandidate(
                        query=query,
                        provider=self.name,
                        rank=rank,
                        url=url,
                        title=item.get("title", "") or "",
                        snippet=item.get("snippet", "") or "",
                    )
                )
        self._record_attempt(query=query, status="OK", result_count=len(candidates))
        return candidates


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(
        self,
        api_key: str | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        retries: int = 2,
        backoff_factor: float = 1.5,
        min_interval_seconds: float = 0.5,
    ) -> None:
        super().__init__(min_interval_seconds=min_interval_seconds)
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.timeout = (connect_timeout, read_timeout)
        self.session = create_robust_session(
            retries=retries,
            backoff_factor=backoff_factor,
        )
        if not self.api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is required for Brave Search.")

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchCandidate]:
        self._wait_for_rate_limit()
        try:
            response = self.session.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            self._record_attempt(query=query, status="TIMEOUT", error=str(exc))
            return []
        except requests.RequestException as exc:
            self._record_attempt(query=query, status="REQUEST_ERROR", error=str(exc))
            return []
        except ValueError as exc:
            self._record_attempt(query=query, status="INVALID_JSON", error=str(exc))
            return []

        results = payload.get("web", {}).get("results", [])
        candidates = []
        for rank, item in enumerate(results[:max_results], start=1):
            url = item.get("url", "")
            if url:
                candidates.append(
                    SearchCandidate(
                        query=query,
                        provider=self.name,
                        rank=rank,
                        url=url,
                        title=item.get("title", "") or "",
                        snippet=item.get("description", "") or "",
                    )
                )
        self._record_attempt(query=query, status="OK", result_count=len(candidates))
        return candidates


def collect_candidates(
    provider: SearchProvider,
    queries: Iterable[str],
    max_results_per_query: int = 5,
    max_urls: int = 12,
) -> list[SearchCandidate]:
    query_list = list(queries)
    if not query_list or max_urls <= 0:
        return []

    # Spread the URL budget across distinct queries so the first query cannot
    # crowd out alternative organisation aliases.
    per_query_limit = max(
        1,
        min(
            max_results_per_query,
            (max_urls + len(query_list) - 1) // len(query_list),
        ),
    )

    candidates: list[SearchCandidate] = []
    seen_urls: set[str] = set()
    for query in query_list:
        for candidate in provider.search(query, max_results=per_query_limit):
            if candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            candidates.append(candidate)
            if len(candidates) >= max_urls:
                return candidates
    return candidates
