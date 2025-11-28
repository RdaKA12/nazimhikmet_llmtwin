"""Normalization step for ETL pipeline."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Iterable, List

from ...crawler.utils.text import clean, now

DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"]


def normalize_records(records: Iterable[dict]) -> List[dict]:
    """Normalize text fields, default metadata, and format dates."""
    normalized: List[dict] = []
    for record in records:
        item = deepcopy(record)
        item["title"] = clean(item.get("title", ""))
        item["summary"] = clean(item.get("summary", ""))
        text_full = item.get("text_full", "")
        if isinstance(text_full, str):
            item["text_full"] = text_full.strip()
        item["lang"] = item.get("lang") or "tr"
        item["type"] = item.get("type") or item.get("work_type") or "unknown"
        item["date"] = _normalize_date(item.get("date"))
        if "year" in item and isinstance(item["year"], str):
            try:
                item["year"] = int(item["year"])
            except ValueError:
                item["year"] = None
        item.setdefault("author", "Nazim Hikmet")
        item.setdefault("license", "unknown")
        item.setdefault("created_at", now())
        normalized.append(item)
    return normalized


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Already ISO
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.date().isoformat()
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue
    # Year only fallback
    if len(value) == 4 and value.isdigit():
        return f"{value}-01-01"
    return value
