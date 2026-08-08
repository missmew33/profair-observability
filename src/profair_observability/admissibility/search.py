from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from typing import Iterable

import requests
from unidecode import unidecode

from .schema import SearchCandidate


def _clean(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"nan", "none"} else text


def organisation_target(row: dict) -> str:
    for key in ("org_search_target", "trade_name", "account_name"):
        value = _clean(row.get(key, ""))
        if value:
            return value
    return ""


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
        org = organisation_target(row)
        country = _clean(row.get("country_code", ""))
        trade_name = _clean(row.get("trade_name", ""))
        account_name = _clean(row.get("account_name", ""))
        if not full_name:
            return []
        names = name_variants(full_name)
        org_variants = []
        for value in (org, trade_name, account_name):
            if value and value.casefold() not in {x.casefold() for x in org_variants}:
                org_variants.append(value)
        queries = []
        for name in names:
            if org_variants:
                queries.append(f'"{name}" "{org_variants[0]}"')
                queries.append(f'"{name}" {org_variants[0]}')
            else:
                queries.append(f'"{name}"')
        if len(org_variants) > 1:
            queries.append(f'"{names[0]}" "{org_variants[1]}"')
        if country and org:
            queries.append(f'"{names[0]}" "{org}" {country}')
        unique, seen = [], set()
        for q in queries:
            key = q.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(q)
        return unique[: self.max_queries]


class SearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[SearchCandidate]:
        raise NotImplementedError


class SerpAPISearchProvider(SearchProvider):
    name = "serpapi"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0) -> None:
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is required for SerpAPI search.")

    def search(self, query: str, max_results: int = 5) -> list[SearchCandidate]:
        response = requests.get("https://serpapi.com/search.json", params={"engine": "google", "q": query, "api_key": self.api_key, "num": max_results}, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        candidates = []
        for rank, item in enumerate(payload.get("organic_results", [])[:max_results], start=1):
            url = item.get("link", "")
            if url:
                candidates.append(SearchCandidate(query=query, provider=self.name, rank=rank, url=url, title=item.get("title", "") or "", snippet=item.get("snippet", "") or ""))
        return candidates


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0) -> None:
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY", "")
        self.timeout = timeout
        if not self.api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is required for Brave Search.")

    def search(self, query: str, max_results: int = 5) -> list[SearchCandidate]:
        response = requests.get("https://api.search.brave.com/res/v1/web/search", params={"q": query, "count": max_results}, headers={"Accept": "application/json", "X-Subscription-Token": self.api_key}, timeout=self.timeout)
        response.raise_for_status()
        results = response.json().get("web", {}).get("results", [])
        candidates = []
        for rank, item in enumerate(results[:max_results], start=1):
            url = item.get("url", "")
            if url:
                candidates.append(SearchCandidate(query=query, provider=self.name, rank=rank, url=url, title=item.get("title", "") or "", snippet=item.get("description", "") or ""))
        return candidates


def collect_candidates(provider: SearchProvider, queries: Iterable[str], max_results_per_query: int = 5, max_urls: int = 12) -> list[SearchCandidate]:
    candidates, seen_urls = [], set()
    for query in queries:
        for candidate in provider.search(query, max_results=max_results_per_query):
            if candidate.url in seen_urls:
                continue
            seen_urls.add(candidate.url)
            candidates.append(candidate)
            if len(candidates) >= max_urls:
                return candidates
    return candidates
