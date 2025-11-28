"""Lightweight ODM utilities for MongoDB documents."""
from __future__ import annotations

from src.domain.documents import (
    DOCUMENT_REGISTRY,
    BookDocument,
    build_document,
    NewsDocument,
    NoSQLBaseDocument,
    NovelDocument,
    PdfPoemDocument,
    PlayDocument,
    PoemListDocument,
    PoemPageDocument,
    ValidationError,
    resolve_document_class,
)

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
    "build_document",
    "resolve_document_class",
]
