from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .schema import RetrievedSource, RetrievalStatus, SearchCandidate

DEFAULT_TIMEOUT = 10.0
MAX_CONTENT_LENGTH = 2_000_000
MAX_PDF_CONTENT_LENGTH = 8_000_000
SAFE_UNWANTED_TAGS = ["script", "style", "noscript", "svg", "iframe", "form", "button"]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _host_is_public(hostname: str) -> bool:
    if not hostname or hostname.lower() in {"localhost", "localhost.localdomain"}:
        return False
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return False
    return True


def clean_html(html: str) -> tuple[str, str]:
    if not html.strip():
        return "", ""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    for tag in soup(SAFE_UNWANTED_TAGS):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    return text, title


def extract_pdf_text(content: bytes) -> str:
    """Extract embedded PDF text only; OCR is deliberately out of scope."""
    reader = PdfReader(BytesIO(content), strict=False)
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text)
    return re.sub(r"\s+", " ", " ".join(pages)).strip()


class SourceRetriever:
    def __init__(self, cache_dir: str | os.PathLike[str] = ".profair_cache", timeout: float = DEFAULT_TIMEOUT, max_content_length: int = MAX_CONTENT_LENGTH, max_pdf_content_length: int = MAX_PDF_CONTENT_LENGTH, per_domain_delay: float = 0.4) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.max_pdf_content_length = max_pdf_content_length
        self.per_domain_delay = per_domain_delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ProFairResearchBot/2.2.8; +https://github.com/missmew33/profair-observability)"})
        self._last_request_by_host: dict[str, float] = {}

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{sha256_text(url)}.json"

    def _load_cache(self, candidate: SearchCandidate) -> RetrievedSource | None:
        path = self._cache_path(candidate.url)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["query"] = candidate.query
            data["provider"] = candidate.provider
            data["rank"] = candidate.rank
            data["from_cache"] = True
            return RetrievedSource(**data)
        except (OSError, ValueError, TypeError):
            return None

    def _save_cache(self, record: RetrievedSource) -> None:
        path = self._cache_path(record.requested_url)
        data = {field: getattr(record, field) for field in record.__dataclass_fields__}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _rate_limit(self, hostname: str) -> None:
        now = time.monotonic()
        last = self._last_request_by_host.get(hostname, 0.0)
        wait = self.per_domain_delay - (now - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request_by_host[hostname] = time.monotonic()

    def fetch(self, candidate: SearchCandidate, use_cache: bool = True) -> RetrievedSource:
        if use_cache:
            cached = self._load_cache(candidate)
            if cached is not None:
                return cached
        record = RetrievedSource(query=candidate.query, provider=candidate.provider, rank=candidate.rank, requested_url=candidate.url, retrieved_at=_now_utc())
        parsed = urlparse(candidate.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            record.retrieval_status = RetrievalStatus.INVALID_URL.value
            record.error_message = "URL must use http/https and contain a hostname."
            return record
        if not _host_is_public(parsed.hostname):
            record.retrieval_status = RetrievalStatus.BLOCKED.value
            record.error_message = "Local/private/reserved network destination rejected."
            return record
        self._rate_limit(parsed.hostname)
        try:
            response = self.session.get(candidate.url, timeout=self.timeout, stream=True, allow_redirects=True)
            record.http_status = response.status_code
            record.final_url = response.url
            final = urlparse(response.url)
            if not final.hostname or not _host_is_public(final.hostname):
                record.retrieval_status = RetrievalStatus.BLOCKED.value
                record.error_message = "Redirect target resolved to a local/private/reserved destination."
                return record
            if response.status_code in {403, 429}:
                record.retrieval_status = RetrievalStatus.BLOCKED.value
                record.error_message = f"HTTP {response.status_code}"
                return record
            if response.status_code != 200:
                record.retrieval_status = RetrievalStatus.HTTP_ERROR.value
                record.error_message = f"HTTP {response.status_code}"
                return record

            content_type = response.headers.get("Content-Type", "").lower()
            record.content_type = content_type
            is_pdf = "application/pdf" in content_type or response.url.lower().endswith(".pdf")
            is_text = any(kind in content_type for kind in ("text/html", "text/plain", "application/xhtml+xml"))
            if not is_pdf and not is_text:
                record.retrieval_status = RetrievalStatus.NON_TEXT_RESOURCE.value
                record.error_message = f"Unsupported content type: {content_type or 'unknown'}"
                return record

            max_length = self.max_pdf_content_length if is_pdf else self.max_content_length
            header_len = response.headers.get("Content-Length")
            if header_len:
                try:
                    if int(header_len) > max_length:
                        record.retrieval_status = RetrievalStatus.CONTENT_TOO_LARGE.value
                        record.error_message = "Content-Length exceeds configured maximum."
                        return record
                except ValueError:
                    pass

            content = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > max_length:
                    record.retrieval_status = RetrievalStatus.CONTENT_TOO_LARGE.value
                    record.error_message = "Downloaded body exceeded configured maximum."
                    return record

            if is_pdf:
                try:
                    text = extract_pdf_text(bytes(content))
                except Exception as exc:
                    record.retrieval_status = RetrievalStatus.NON_TEXT_RESOURCE.value
                    record.error_message = f"PDF text extraction failed: {type(exc).__name__}"
                    return record
                if len(text) < 100:
                    record.retrieval_status = RetrievalStatus.NON_TEXT_RESOURCE.value
                    record.error_message = "PDF contained insufficient extractable embedded text; OCR not used."
                    return record
                record.full_text = text
                record.page_title = candidate.title
                record.content_sha256 = sha256_text(text)
                record.retrieval_status = RetrievalStatus.FULL_TEXT_RETRIEVED.value
                self._save_cache(record)
                return record

            raw = bytes(content).decode(response.encoding or "utf-8", errors="replace")
            text, title = clean_html(raw)
            if len(text) < 100:
                record.retrieval_status = RetrievalStatus.JS_OR_EMPTY_PAGE.value
                record.error_message = "Extracted visible text below 100 characters."
                return record
            record.full_text = text
            record.page_title = title
            record.content_sha256 = sha256_text(text)
            record.retrieval_status = RetrievalStatus.FULL_TEXT_RETRIEVED.value
            self._save_cache(record)
            return record
        except requests.Timeout:
            record.retrieval_status = RetrievalStatus.TIMEOUT.value
            record.error_message = "Network timeout."
            return record
        except requests.RequestException as exc:
            record.retrieval_status = RetrievalStatus.HTTP_ERROR.value
            record.error_message = str(exc)
            return record

    def fetch_many(self, candidates: list[SearchCandidate], use_cache: bool = True) -> list[RetrievedSource]:
        return [self.fetch(candidate, use_cache=use_cache) for candidate in candidates]
