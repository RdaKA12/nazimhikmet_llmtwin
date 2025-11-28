"""Domain document models shared across ingestion components."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Type


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ValidationError(ValueError):
    """Raised when an ODM document fails validation."""


class NoSQLBaseDocument:
    """Base document that enforces lightweight schema and metadata defaults."""

    kind: str = "generic"
    collection_name: str = "documents"
    required_fields: tuple[str, ...] = ("title",)
    upsert_fields: tuple[str, ...] = ("kind", "source_id")

    def __init__(self, payload: Mapping[str, Any]):
        if not isinstance(payload, Mapping):
            raise ValidationError("Document payload must be a mapping.")
        raw = dict(payload)
        self.data = self._apply_defaults(raw)
        self.validate()

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "NoSQLBaseDocument":
        return cls(payload)

    def _apply_defaults(self, document: Dict[str, Any]) -> Dict[str, Any]:
        data = deepcopy(document)
        data.setdefault("kind", self.kind)

        source_id = data.get("source_id") or data.get("hash") or data.get("source_url")
        if not source_id:
            raise ValidationError(f"{self.kind} document requires a 'hash' or 'source_id'.")
        data["source_id"] = source_id

        source_meta = data.get("source")
        if not isinstance(source_meta, dict):
            source_meta = {}
        if data.get("source_name") and not source_meta.get("name"):
            source_meta["name"] = data["source_name"]
        if data.get("source_url") and not source_meta.get("url"):
            source_meta["url"] = data["source_url"]
        data["source"] = source_meta

        created_at = data.get("created_at")
        if not created_at:
            created_at = _now_iso()
        data["created_at"] = created_at
        data["updated_at"] = _now_iso()
        return data

    def validate(self) -> None:
        missing_required = [field for field in self.required_fields if not self.data.get(field)]
        if missing_required:
            raise ValidationError(
                f"{self.kind} document missing required fields: {', '.join(missing_required)}"
            )
        for field in self.upsert_fields:
            if not self.data.get(field):
                raise ValidationError(f"{self.kind} document missing upsert field '{field}'.")

    def upsert_filter(self) -> Dict[str, Any]:
        return {field: self.data[field] for field in self.upsert_fields}

    def to_mongo(self) -> Dict[str, Any]:
        payload = deepcopy(self.data)
        payload["updated_at"] = _now_iso()
        return payload


class PoemPageDocument(NoSQLBaseDocument):
    kind = "poem_page"
    required_fields = ("title",)

    def validate(self) -> None:
        super().validate()
        if not (self.data.get("text_full") or self.data.get("summary")):
            raise ValidationError("poem_page document requires text_full or summary content.")


class PdfPoemDocument(NoSQLBaseDocument):
    kind = "pdf_poems"
    required_fields = ("title",)

    def validate(self) -> None:
        super().validate()
        if not (self.data.get("text_full") or self.data.get("summary")):
            raise ValidationError("pdf_poems document requires text_full or summary content.")


class PoemListDocument(NoSQLBaseDocument):
    kind = "poem"
    required_fields = ("title",)


class BookDocument(NoSQLBaseDocument):
    kind = "book"
    required_fields = ("title",)


class NovelDocument(BookDocument):
    kind = "novel"


class PlayDocument(NoSQLBaseDocument):
    kind = "play"
    required_fields = ("title",)


class NewsDocument(NoSQLBaseDocument):
    kind = "news"
    required_fields = ("title",)

    def validate(self) -> None:
        super().validate()
        if not (self.data.get("text_full") or self.data.get("summary")):
            raise ValidationError("news document requires text_full or summary content.")


DOCUMENT_REGISTRY: Dict[str, Type[NoSQLBaseDocument]] = {
    cls.kind: cls
    for cls in (
        PoemPageDocument,
        PdfPoemDocument,
        PoemListDocument,
        BookDocument,
        NovelDocument,
        PlayDocument,
        NewsDocument,
    )
}


def resolve_document_class(kind: str) -> Type[NoSQLBaseDocument]:
    try:
        return DOCUMENT_REGISTRY[kind]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValidationError(f"No document registered for kind '{kind}'.") from exc


def build_document(record: Mapping[str, Any]) -> NoSQLBaseDocument:
    """Construct a typed document instance from a raw record mapping."""
    kind = record.get("kind")
    if not kind:
        raise ValidationError("Record is missing 'kind'; unable to select ODM document.")
    document_cls = DOCUMENT_REGISTRY.get(kind)
    if document_cls is None:
        document_cls = resolve_document_class(kind)
    return document_cls.from_payload(record)


__all__ = [
    "DOCUMENT_REGISTRY",
    "NoSQLBaseDocument",
    "PoemPageDocument",
    "PdfPoemDocument",
    "BookDocument",
    "NovelDocument",
    "PlayDocument",
    "NewsDocument",
    "PoemListDocument",
    "ValidationError",
    "resolve_document_class",
    "build_document",
]
