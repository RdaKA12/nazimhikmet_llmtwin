from __future__ import annotations

from typing import Any, Dict, Tuple

import pytest

from src.etl.steps import store as store_module


class FakeUpdateResult:
    def __init__(self, upserted_id: int | None):
        self.upserted_id = upserted_id


class FakeCollection:
    def __init__(self) -> None:
        self.storage: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def update_one(self, filter_doc: Dict[str, Any], update_doc: Dict[str, Any], upsert: bool = False):
        key = (filter_doc["kind"], filter_doc["source_id"])
        existing = self.storage.get(key)
        if existing is None:
            if not upsert:
                raise AssertionError("Expected upsert=True for inserts.")
            document = dict(update_doc.get("$set", {}))
            if "$setOnInsert" in update_doc:
                document.update(update_doc["$setOnInsert"])
            self.storage[key] = document
            return FakeUpdateResult(upserted_id=len(self.storage))

        existing.update(update_doc.get("$set", {}))
        self.storage[key] = existing
        return FakeUpdateResult(upserted_id=None)


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: Dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class FakeMongoClient:
    last_instance: "FakeMongoClient | None" = None

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.databases: Dict[str, FakeDatabase] = {}
        FakeMongoClient.last_instance = self

    def __getitem__(self, name: str) -> FakeDatabase:
        if name not in self.databases:
            self.databases[name] = FakeDatabase()
        return self.databases[name]


@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(store_module, "MongoClient", FakeMongoClient)
    yield
    FakeMongoClient.last_instance = None


def _get_stored_document(kind: str, source_id: str) -> Dict[str, Any]:
    client = FakeMongoClient.last_instance
    assert client is not None, "MongoClient was not initialised"
    collection = client["digital_twin"]["documents"]
    return collection.storage[(kind, source_id)]


def test_store_records_upsert_and_update() -> None:
    record = {
        "kind": "poem_page",
        "title": "Kiz Cocugu",
        "text_full": "Stillenecektir dünya",
        "hash": "poem-1",
    }

    inserted = store_module.store_records([record], "mongodb://fake")
    assert inserted == 1
    stored = _get_stored_document("poem_page", "poem-1")
    created_at_first = stored["created_at"]
    updated_at_first = stored["updated_at"]

    updated_record = {
        "kind": "poem_page",
        "title": "Kiz Cocugu",
        "summary": "Özet versiyon",
        "hash": "poem-1",
    }

    inserted_again = store_module.store_records([updated_record], "mongodb://fake")
    assert inserted_again == 0
    stored_after = _get_stored_document("poem_page", "poem-1")

    assert stored_after["created_at"] == created_at_first
    assert stored_after["updated_at"] != updated_at_first
    assert stored_after["summary"] == "Özet versiyon"
    assert stored_after["kind"] == "poem_page"
