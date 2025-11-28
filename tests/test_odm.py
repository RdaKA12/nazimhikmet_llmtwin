from __future__ import annotations

import pytest

from src.etl.odm import (
    NewsDocument,
    PoemPageDocument,
    ValidationError,
)


def test_poem_page_document_uses_hash_for_source_id() -> None:
    payload = {
        "title": "Kız Çocuğu",
        "text_full": "Kız çocuğu akşam vakti...",
        "hash": "abc123",
    }
    document = PoemPageDocument(payload)
    assert document.data["source_id"] == "abc123"
    assert document.data["kind"] == "poem_page"
    assert {"kind", "source_id"} == set(document.upsert_filter().keys())


def test_poem_page_document_requires_content() -> None:
    with pytest.raises(ValidationError):
        PoemPageDocument({"title": "Eksik", "hash": "123"})


def test_news_document_allows_summary_when_text_full_missing() -> None:
    payload = {
        "title": "Nazım Hikmet Haber",
        "summary": "Kısa özet",
        "hash": "news1",
    }
    document = NewsDocument(payload)
    assert document.data["summary"] == "Kısa özet"
    assert document.data["kind"] == "news"
