"""Persistence step for ETL pipeline."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable

from src.domain.documents import build_document

try:  # pragma: no cover - prefer real pymongo when available
    from pymongo import MongoClient  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for test environments
    class MongoClient:  # type: ignore
        def __init__(self, *_args, **_kwargs) -> None:
            raise ModuleNotFoundError("pymongo is required to store records")

LOGGER = logging.getLogger(__name__)


def store_records(
    records: Iterable[dict],
    mongo_url: str,
    *,
    db_name: str = "digital_twin",
    collection: str = "documents",
) -> int:
    """Persist records into MongoDB via ODM documents and return inserted count."""
    raw_records = list(records)
    if not raw_records:
        return 0

    documents = [build_document(record) for record in raw_records]

    client = MongoClient(mongo_url)
    database = client[db_name]

    collections_cache: Dict[str, Any] = {}
    inserted = 0

    for document in documents:
        collection_name = document.collection_name or collection
        mongo_collection = collections_cache.get(collection_name)
        if mongo_collection is None:
            mongo_collection = database[collection_name]
            collections_cache[collection_name] = mongo_collection

        payload = document.to_mongo()
        created_at = payload.pop("created_at", None)
        update_doc = {"$set": payload}
        if created_at:
            update_doc.setdefault("$setOnInsert", {})["created_at"] = created_at

        result = mongo_collection.update_one(document.upsert_filter(), update_doc, upsert=True)
        if getattr(result, "upserted_id", None) is not None:
            inserted += 1

    LOGGER.info("Upserted %s new documents into %s", inserted, db_name)
    return inserted
