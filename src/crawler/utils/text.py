"""Utility helpers for working with text and metadata."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone

SIIR_ARSIVI_TOKENS = {"siir arsivi"}
YEAR_RE = re.compile(r"(18|19|20)\d{2}")


def normalize_token(text: str) -> str:
    """Return a lowercase string without diacritics for comparisons."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.lower()


def clean(text: str) -> str:
    """Normalize whitespace while preserving line breaks and trim site tokens."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\u00A0", " ").replace("\u200b", "")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in normalized.splitlines()]
    joined = "\n".join(lines)
    cleaned = joined.strip()
    if not cleaned:
        return ""
    token = normalize_token(cleaned)
    if token in SIIR_ARSIVI_TOKENS:
        return ""
    return cleaned


def canonicalize(text: str) -> str:
    """Lowercase and normalize spacing/punctuation for stable hashing."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00A0", " ").replace("\u200b", "")
    normalized = normalized.replace("\u2019", "'").replace("\u2018", "'")
    normalized = normalized.replace("\u201C", '\"').replace("\u201D", '\"')
    normalized = normalized.replace("\u2013", "-").replace("\u2014", "-")
    lines = [re.sub(r"\s+", " ", line).strip() for line in normalized.splitlines()]
    canonical = " \n ".join(line for line in lines if line)
    canonical = re.sub(r"[ \t]+", " ", canonical)
    return canonical.strip().lower()


def now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def mkhash(*parts: str) -> str:
    """Build a deterministic hash from the given string parts."""
    joined = "|".join(part or "" for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return digest


def year_from_text(text: str) -> int | None:
    """Extract the first four digit year from text if present."""
    if not text:
        return None
    match = YEAR_RE.search(text)
    if match:
        return int(match.group(0))
    return None
