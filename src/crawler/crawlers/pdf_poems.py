"""Crawler that extracts literary works from a PDF source."""
import io
import re
import ssl
import time
import unicodedata
from typing import Any, Dict, Iterable, List, Match, Optional, Set, Tuple, Union
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

from ..base import BaseCrawler
from ..dispatcher import register_crawler
from ..utils.fetch import DEFAULT_HEADERS
from ..utils.text import clean, mkhash, now


DEFAULT_AUTHOR = "Nazim Hikmet"
DEFAULT_COLLECTION = "Nazim Hikmet PDF Collection"
DEFAULT_LANG = "tr"
DEFAULT_DOCUMENT_TYPE = "poem"
DEFAULT_WORK_TYPE = "poem"

CID_REPLACEMENTS: Dict[str, str] = {
    "213": "ı",
    "247": "ğ",
    "250": "ş",
    "248": "İ",
    "249": "Ş",
    "80": "n",
    "81": "n",
    "85": "z",
    "86": "n",
    "92": "y",
    "93": "l",
    "79": "ğ",
    "46": "Ö",
    "36": "Ç",
    "44": "ış",
    "56": "Şaf",
    "60": "Y",
    "68": "gü",
    "71": "dır",
    "72": "i",
    "76": "İş",
    "78": "kı",
    "3": " ş",
    "246": "Ğ",
}
CID_PATTERN = re.compile(r"\(cid:(\d+)\)")


HEADER_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"^\s*\d{1,4}\s*$"),
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"mustafa\s*altini?sik", re.IGNORECASE),
    re.compile(r"www\.", re.IGNORECASE),
]


class _LegacyTLSAdapter(HTTPAdapter):
    """HTTP adapter that relaxes TLS cipher requirements for legacy servers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, max_retries=0, **kwargs)

    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> None:
        pool_kwargs["ssl_context"] = self._build_context()
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)

    def proxy_manager_for(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        kwargs.setdefault("proxy_kwargs", {})
        kwargs["proxy_kwargs"]["ssl_context"] = self._build_context()
        return super().proxy_manager_for(*args, **kwargs)

    @staticmethod
    def _build_context() -> ssl.SSLContext:
        context = ssl.create_default_context()
        try:
            context.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            # Fall back to default ciphers when the platform forbids lowering the security level.
            pass
        # When requests disables certificate verification for legacy hosts, ensure hostname checks
        # are also disabled; otherwise Python raises ValueError when switching to CERT_NONE.
        context.check_hostname = False
        return context


class PdfPoemsCrawler(BaseCrawler):
    """Crawler that reads Nazim Hikmet works from a PDF source."""

    kind = "pdf_poems"

    def __init__(self, config: Dict, safe_mode: bool = False) -> None:
        super().__init__(config, safe_mode=safe_mode)
        self._session = self._build_session()
        self._seen_hashes: Set[str] = set()

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        adapter = _LegacyTLSAdapter()
        session.mount("https://", adapter)
        session.mount("http://", HTTPAdapter(max_retries=0))
        return session

    def parse(self, html: str, url: str, **_: dict) -> Iterable[dict]:
        """Unused HTML parser hook kept for compatibility with BaseCrawler."""
        return []

    def extract(self, link: str, user: str, **_: Any) -> List[Dict[str, Any]]:  # type: ignore[override]
        pdf_url = (link or "").strip()
        if not pdf_url:
            self.logger.warning("PdfPoemsCrawler received empty link for %s", self.config.get("name", self.kind))
            return []

        try:
            pdf_bytes = self.fetch_bytes(pdf_url)
        except Exception as exc:  # pragma: no cover - network/IO failure
            self.logger.error("Failed to download PDF %s: %s", pdf_url, exc, exc_info=True)
            return []

        extracted: List[Dict[str, Any]] = []
        poems = self._parse_pdf(pdf_bytes, pdf_url)
        for poem in poems:
            doc_hash = poem.get("hash")
            if doc_hash and doc_hash in self._seen_hashes:
                continue
            if doc_hash:
                self._seen_hashes.add(doc_hash)
            payload = self._finalize_payload(poem, link=pdf_url, user=user)
            extracted.append(payload)

        if extracted:
            self.logger.info("Extracted %d records from %s", len(extracted), pdf_url)
        return extracted

    def fetch_bytes(self, url: str, timeout: Union[int, Tuple[int, int]] = 60, *, allow_fallback: bool = True) -> bytes:
        timeout_value = self._resolve_timeout(timeout)
        retries = max(1, int(self.config.get("fetch_retries", self.max_retries)))
        backoff_base = float(self.config.get("fetch_backoff_base", self.backoff_base))
        backoff_factor = float(self.config.get("fetch_backoff_factor", self.backoff_factor))
        verify = self._resolve_verify_ssl()

        safe_url = requests.utils.requote_uri(url)
        if safe_url != url:
            self.logger.debug("Normalized URL for request: %s -> %s", url, safe_url)

        request_url = safe_url
        last_exc: Optional[Exception] = None
        for attempt in range(retries):
            try:
                response = self._session.get(request_url, timeout=timeout_value, verify=verify, stream=True)
                try:
                    response.raise_for_status()
                    content = response.content
                    if not content:
                        content = b"".join(response.iter_content(chunk_size=8192))
                    return content
                finally:
                    response.close()
            except requests.RequestException as exc:  # pragma: no cover - network/SSL variability
                last_exc = exc
                if attempt + 1 >= retries:
                    break
                wait_for = backoff_base * (backoff_factor ** attempt)
                self.logger.warning(
                    "Retrying download %s (attempt %s/%s): %s", url, attempt + 1, retries, exc
                )
                time.sleep(wait_for)

        if allow_fallback and self._should_try_http_fallback(request_url):
            fallback_url = "http://" + request_url[len("https://") :]
            fallback_url = requests.utils.requote_uri(fallback_url)
            self.logger.warning("HTTPS failed for %s; attempting HTTP fallback %s", request_url, fallback_url)
            return self.fetch_bytes(fallback_url, timeout=timeout, allow_fallback=False)

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Failed to fetch {request_url}")

    def _parse_pdf(self, pdf_bytes: bytes, source_url: str) -> List[Dict[str, Any]]:
        try:
            import pdfplumber  # type: ignore
        except ModuleNotFoundError:
            self.logger.error("pdfplumber is not installed; skipping PDF crawler run.")
            return []

        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
        except Exception as exc:  # pragma: no cover - parsing failure
            self.logger.warning("Could not open PDF %s: %s", source_url, exc, exc_info=True)
            return []

        lines = self._collect_lines(pages)
        poems = self._split_poems(lines, source_url)
        return poems

    def _collect_lines(self, pages: List[str]) -> List[str]:
        lines: List[str] = []
        for page_text in pages:
            normalized_page = page_text.replace("\r\n", "\n").replace("\r", "\n")
            normalized_page = normalized_page.replace("\ufb01", "fi").replace("\ufb02", "fl")
            normalized_page = unicodedata.normalize("NFKC", normalized_page)
            for raw_line in normalized_page.split("\n"):
                normalized_line = unicodedata.normalize("NFKC", raw_line)
                line = re.sub(r"[ \t]+", " ", normalized_line).strip()
                line = self._replace_cid_sequences(line)
                if not line:
                    lines.append("")
                    continue
                lowered = line.lower()
                if self._is_header_line(line, lowered):
                    continue
                lines.append(line)
            if lines and lines[-1] != "":
                lines.append("")
        return lines

    def _is_header_line(self, line: str, lowered: Optional[str] = None) -> bool:
        lowered = lowered or line.lower()
        if "nazim" in lowered and "hikmet" in lowered:
            return True
        for pattern in HEADER_PATTERNS:
            if pattern.search(line):
                return True
        return False

    def _split_poems(self, lines: List[str], source_url: str) -> List[Dict[str, Any]]:
        title_indices = self._detect_title_indices(lines)
        if not title_indices:
            normalized_text = self._normalize_poem_text("\n".join(lines))
            if not normalized_text:
                return []
            title = normalized_text.splitlines()[0][:60]
            return [self._build_document(title, normalized_text, source_url)]

        documents: List[Dict[str, Any]] = []
        for idx, title_idx in enumerate(title_indices):
            title_text, body_start = self._collect_title_block(lines, title_idx)
            while body_start < len(lines) and not lines[body_start].strip():
                body_start += 1
            next_title_idx = title_indices[idx + 1] if idx + 1 < len(title_indices) else len(lines)
            body_lines = lines[body_start:next_title_idx]
            while body_lines and not body_lines[-1].strip():
                body_lines.pop()
            poem_raw = "\n".join(body_lines)
            normalized_text = self._normalize_poem_text(poem_raw)
            if not normalized_text:
                continue
            title_candidate = title_text or ""
            if not title_candidate and normalized_text:
                title_candidate = normalized_text.splitlines()[0][:60]
            documents.append(self._build_document(title_candidate, normalized_text, source_url))
        return documents


    def _detect_title_indices(self, lines: List[str]) -> List[int]:
        indices: List[int] = []
        for idx, line in enumerate(lines):
            if not line.strip():
                continue
            if idx > 0 and lines[idx - 1].strip():
                continue
            if self._is_title_candidate(line, lines, idx):
                indices.append(idx)
        return indices

    def _is_title_candidate(self, line: str, lines: List[str], idx: int) -> bool:
        stripped = line.strip()
        if not (3 <= len(stripped) <= 60):
            return False
        next_non_empty = self._next_non_empty_line(lines, idx)
        if not next_non_empty:
            return False
        letters = [ch for ch in stripped if ch.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        punctuation_count = sum(1 for ch in stripped if ch in ",.;:!?")
        if punctuation_count > max(2, len(stripped) // 3):
            return False
        title_case = stripped.istitle()
        capitalized_words = all(word[:1].isupper() for word in stripped.split() if word and word[:1].isalpha())
        return stripped.isupper() or upper_ratio >= 0.65 or title_case or capitalized_words

    def _next_non_empty_line(self, lines: List[str], idx: int) -> Optional[str]:
        for pos in range(idx + 1, len(lines)):
            candidate = lines[pos]
            if candidate.strip():
                return candidate
        return None

    def _collect_title_block(self, lines: List[str], idx: int) -> Tuple[str, int]:
        parts: List[str] = []
        current = idx
        while current < len(lines):
            candidate = lines[current].strip()
            if not candidate:
                break
            if current != idx and not self._is_title_continuation(candidate):
                break
            parts.append(candidate)
            current += 1
        title_text = " ".join(parts)
        return title_text, current

    def _is_title_continuation(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            return False
        letters = [ch for ch in stripped if ch.isalpha()]
        if not letters:
            return False
        upper_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        if upper_ratio >= 0.6:
            return True
        words = [word for word in stripped.split() if any(ch.isalpha() for ch in word)]
        if len(words) <= 4 and all(word[0].isupper() or not word[0].isalpha() for word in words if word):
            return True
        return False

    def _normalize_poem_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = self._replace_cid_sequences(normalized)
        normalized_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.split("\n")]
        cleaned = "\n".join(normalized_lines)
        cleaned = cleaned.replace("\u201C", '"').replace("\u201D", '"')
        cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
        cleaned = cleaned.replace("\u2013", "-").replace("\u2014", "-")
        cleaned = clean(cleaned)
        if not cleaned:
            return ""
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = unicodedata.normalize("NFC", cleaned.strip())
        return cleaned

    def _build_document(self, title: str, text: str, source_url: str) -> Dict[str, Any]:
        normalized_title = unicodedata.normalize("NFC", title) if title else ""
        safe_title = clean(normalized_title).strip() if normalized_title else ""
        normalized_text = unicodedata.normalize("NFC", text)
        if not safe_title and normalized_text:
            safe_title = normalized_text.splitlines()[0][:60]
        domain = urlparse(source_url).netloc or source_url
        doc_hash = mkhash(source_url, safe_title, normalized_text)
        metadata = self._document_metadata()
        return {
            "type": metadata["type"],
            "work_type": metadata["work_type"],
            "lang": metadata["lang"],
            "author": metadata["author"],
            "title": safe_title,
            "text_full": normalized_text,
            "summary": "",
            "collection": metadata["collection"],
            "source_url": source_url,
            "source_name": domain,
            "license": "unknown",
            "hash": doc_hash,
            "created_at": now(),
        }

    def _document_metadata(self) -> Dict[str, str]:
        return {
            "type": self.config.get("document_type", DEFAULT_DOCUMENT_TYPE),
            "work_type": self.config.get("work_type", DEFAULT_WORK_TYPE),
            "lang": self.config.get("lang", DEFAULT_LANG),
            "author": self.config.get("author", DEFAULT_AUTHOR),
            "collection": self.config.get("collection", self.config.get("name", DEFAULT_COLLECTION)),
        }

    def _resolve_timeout(self, default_timeout: Union[int, Tuple[int, int]]) -> Union[float, Tuple[float, float]]:
        config_timeout = self.config.get("fetch_timeout")
        if config_timeout is None:
            return self._normalize_timeout(default_timeout)

        if isinstance(config_timeout, (int, float)):
            return float(config_timeout)
        if isinstance(config_timeout, str):
            try:
                return float(config_timeout)
            except ValueError:
                self.logger.warning("Invalid fetch_timeout value %r; using default", config_timeout)
                return self._normalize_timeout(default_timeout)
        if isinstance(config_timeout, (list, tuple)):
            values = list(config_timeout)
            if not values:
                return self._normalize_timeout(default_timeout)
            if len(values) == 1:
                try:
                    return float(values[0])
                except (TypeError, ValueError):
                    self.logger.warning("Invalid fetch_timeout entry %r; using default", values[0])
                    return self._normalize_timeout(default_timeout)
            try:
                return float(values[0]), float(values[1])
            except (TypeError, ValueError):
                self.logger.warning("Invalid fetch_timeout entries %r; using default", values)
                return self._normalize_timeout(default_timeout)
        self.logger.warning("Unsupported fetch_timeout type %s; using default", type(config_timeout))
        return self._normalize_timeout(default_timeout)

    def _normalize_timeout(self, timeout_value: Union[int, float, Tuple[int, int]]) -> Union[float, Tuple[float, float]]:
        if isinstance(timeout_value, tuple):
            return float(timeout_value[0]), float(timeout_value[1])
        return float(timeout_value)

    def _resolve_verify_ssl(self) -> Union[bool, str]:
        verify_setting = self.config.get("verify_ssl", True)
        if isinstance(verify_setting, bool):
            return verify_setting
        if isinstance(verify_setting, (int, float)):
            return bool(verify_setting)
        if isinstance(verify_setting, str):
            lowered = verify_setting.strip().lower()
            if lowered in {"false", "0", "no", "off"}:
                return False
            if lowered in {"true", "1", "yes", "on"}:
                return True
            return verify_setting
        return True

    def _should_try_http_fallback(self, url: str) -> bool:
        if not url.lower().startswith("https://"):
            return False
        return bool(self.config.get("allow_http_fallback", False))

    @staticmethod
    def _replace_cid_sequences(text: str) -> str:
        if "(cid:" not in text:
            return text

        def repl(match: Match[str]) -> str:
            code = match.group(1)
            return CID_REPLACEMENTS.get(code, "")

        return CID_PATTERN.sub(repl, text)



# Commands to test:
# docker compose build crawler && docker compose up -d crawler && docker compose logs -f crawler
# docker compose run --rm --no-deps crawler python -c "from src.crawler.main import run_once; run_once('Nazim Hikmet PDF (Altinisik)')"

register_crawler(PdfPoemsCrawler.kind, PdfPoemsCrawler)
