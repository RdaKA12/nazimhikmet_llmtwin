"""Deduplication step for ETL pipeline."""
from __future__ import annotations

from typing import Iterable, List, Set


def dedupe_records(records: Iterable[dict]) -> List[dict]:
    """Remove records that share the same hash."""
    seen: Set[str] = set()
    unique: List[dict] = []
    for record in records:
        record_hash = record.get("hash")
        if not record_hash:
            unique.append(record)
            continue
        if record_hash in seen:
            continue
        seen.add(record_hash)
        unique.append(record)
    return unique


def simhash_stub(records: Iterable[dict]) -> None:
    """Placeholder for future similarity hashing implementation."""
    return None
