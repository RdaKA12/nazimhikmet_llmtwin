# -*- coding: utf-8 -*-
"""Embedding ingestion pipeline for Nazim Hikmet digital twin content."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

PROSE_CHUNK_SIZE = 1200
PROSE_CHUNK_OVERLAP = 150
POEM_CHUNK_MAX_CHARS = 600

CONTENT_KEYS: tuple[str, ...] = (
    "content",
    "text",
    "text_full",
    "body",
    "full_text",
    "text_body",
    "raw_text",
)

KIND_KEYS: tuple[str, ...] = ("kind", "type", "work_type", "category")
SOURCE_KEYS: tuple[str, ...] = ("source", "source_url", "url", "origin", "source_name")
KIND_TRANSLATION = str.maketrans({"s": "s", "S": "s", "i": "i", "I": "i"})


@dataclass
class ChunkRecord:
    """Container for a chunk ready to be embedded and pushed to Qdrant."""

    point_id: str
    title: str
    kind: str
    source: str
    chunk: str
    author: str
    hash: str | None = None
    metadata: Dict[str, Any] | None = None


def resolve_first_str(data: Dict[str, Any], keys: Sequence[str]) -> str:
    """Return the first non-empty string value found under the provided keys."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return ""


def load_documents(path: Path) -> List[Dict[str, Any]]:
    """Load documents from JSON file, supporting list or dict container."""
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("documents", "items", "data"):
            maybe_docs = data.get(key)
            if isinstance(maybe_docs, list):
                return maybe_docs

    raise ValueError(
        "Unsupported JSON structure. Expected a list of documents or a dictionary "
        "with a 'documents' key."
    )


def clean_text(raw_text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    soup = BeautifulSoup(raw_text or "", "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_poem(text: str) -> List[str]:
    """Chunk poems stanza-aware to preserve rhythm and retrieval precision."""
    cleaned = text.strip()
    if not cleaned:
        return []
    stanzas = [s.strip() for s in cleaned.split("\n\n") if s.strip()]
    chunks: List[str] = []
    buf: List[str] = []
    cur = 0
    for stanza in stanzas:
        stanza_len = len(stanza)
        if cur == 0:
            buf.append(stanza)
            cur += stanza_len
            continue
        if cur + 2 + stanza_len <= POEM_CHUNK_MAX_CHARS:
            buf.append(stanza)
            cur += 2 + stanza_len
        else:
            chunks.append("\n\n".join(buf))
            buf = [stanza]
            cur = stanza_len
    if buf:
        chunks.append("\n\n".join(buf))
    return chunks


def chunk_prose(
    text: str,
    chunk_size: int = PROSE_CHUNK_SIZE,
    overlap: int = PROSE_CHUNK_OVERLAP,
) -> List[str]:
    """Chunk prose text into ~chunk_size segments with overlap, aligning on periods."""
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        window_text = text[start:end]

        if end < length:
            period_index = window_text.rfind(".")
            if period_index != -1 and period_index > chunk_size - 400:
                end = start + period_index + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= length:
            break

        start = max(end - overlap, 0)

        # Guard against infinite loops on very small or period-less texts.
        if start >= end:
            start = end

    return chunks


def prepare_chunks(documents: Sequence[Dict[str, Any]]) -> tuple[List[ChunkRecord], int, int]:
    """Clean, filter, and chunk documents into records ready for embedding."""
    total_dropped = 0
    dropped_short = 0
    chunk_records: List[ChunkRecord] = []

    for index, doc in enumerate(documents):
        raw_content = resolve_first_str(doc, CONTENT_KEYS)
        if not raw_content:
            total_dropped += 1
            continue

        cleaned = clean_text(raw_content)
        if len(cleaned) < 100:
            total_dropped += 1
            dropped_short += 1
            continue

        kind = resolve_first_str(doc, KIND_KEYS) or doc.get("kind", "") or "unknown"
        title = resolve_first_str(doc, ("title",)) or f"Document {index + 1}"
        source = resolve_first_str(doc, SOURCE_KEYS)
        author = resolve_first_str(doc, ("author",)) or doc.get("author") or "Nazim Hikmet"

        doc_hash = doc.get("hash")
        if not doc_hash:
            base = f"{doc.get('source_url','')}{title}{cleaned[:128]}"
            doc_hash = hashlib.sha256(base.encode("utf-8")).hexdigest()

        metadata = {
            "hash": doc_hash,
            "source_url": doc.get("source_url"),
            "source_name": doc.get("source_name"),
            "collection": doc.get("collection"),
            "year": doc.get("year"),
            "language": doc.get("lang") or doc.get("language"),
            "safe_mode": doc.get("safe_mode"),
        }
        metadata = {key: value for key, value in metadata.items() if value not in (None, "")}
        metadata.setdefault("author", author)

        kind_lower = kind.lower()
        kind_normalized = kind_lower.translate(KIND_TRANSLATION)
        if "siir" in kind_normalized or "poem" in kind_normalized:
            chunks = chunk_poem(cleaned)
        else:
            chunks = chunk_prose(cleaned)

        for chunk in chunks:
            record = ChunkRecord(
                point_id=str(uuid.uuid4()),
                title=title,
                kind=kind or "unknown",
                source=source or "unknown",
                chunk=chunk,
                author=author,
                hash=doc_hash,
                metadata=metadata,
            )
            chunk_records.append(record)

    return chunk_records, total_dropped, dropped_short


def batched(iterable: Sequence[Any], batch_size: int) -> Iterable[Sequence[Any]]:
    """Yield successive batches from a sequence."""
    for start in range(0, len(iterable), batch_size):
        yield iterable[start : start + batch_size]


def main() -> None:
    load_dotenv()

    input_path = Path(os.getenv("INPUT_JSON", "digital_twin.documents.json"))
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path

    if not input_path.exists():
        print(f"[ERROR] Input JSON not found at {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        documents = load_documents(input_path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] Failed to read documents: {exc}", file=sys.stderr)
        sys.exit(1)

    chunks, dropped_total, dropped_short = prepare_chunks(documents)
    if not chunks:
        print("[ERROR] No chunks prepared. Nothing to ingest.", file=sys.stderr)
        sys.exit(1)

    model_name = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")
    model = SentenceTransformer(model_name)
    vector_size = model.get_sentence_embedding_dimension()

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    api_key = os.getenv("QDRANT_APIKEY") or None
    collection_name = os.getenv("COLLECTION_NAME", "nazim_embedded")

    client = QdrantClient(host=host, port=port, api_key=api_key)
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=qdrant_models.VectorParams(
            size=vector_size,
            distance=qdrant_models.Distance.COSINE,
        ),
    )

    batch_size = 256
    total_vectors = 0
    total_chars = 0
    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch in tqdm(
        batched(chunks, batch_size),
        total=total_batches,
        desc="Ingesting",
        unit="batch",
    ):
        passages = [f"passage: {record.chunk}" for record in batch]
        embeddings = model.encode(
            passages,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        points = []
        for record, embedding in zip(batch, embeddings):
            payload = {
                "title": record.title,
                "kind": record.kind,
                "source": record.source,
                "author": record.author,
                "chunk": record.chunk,
            }
            if record.hash:
                payload.setdefault("hash", record.hash)
            if record.metadata:
                for key, value in record.metadata.items():
                    if value is None:
                        continue
                    payload.setdefault(key, value)

            points.append(
                qdrant_models.PointStruct(
                    id=record.point_id,
                    vector=embedding.tolist(),
                    payload=payload,
                )
            )

        client.upsert(collection_name=collection_name, points=points)

        total_vectors += len(points)
        total_chars += sum(len(record.chunk) for record in batch)

    avg_chunk_size = total_chars / total_vectors if total_vectors else 0.0

    print(
        "\nIngestion summary:\n"
        f"  Documents processed: {len(documents)}\n"
        f"  Documents dropped (total): {dropped_total}\n"
        f"  Documents dropped (too short): {dropped_short}\n"
        f"  Total chunks inserted: {total_vectors}\n"
        f"  Average chunk size: {avg_chunk_size:.1f} characters\n"
        f"  Collection: {collection_name} @ {host}:{port}\n"
    )


if __name__ == "__main__":
    main()
