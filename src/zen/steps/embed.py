"""Embedding step that reuses the shared ETL chunking utilities."""
import os
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sentence_transformers import SentenceTransformer
from typing_extensions import Annotated
from zenml import step

from src.etl.ingest_embeddings import ChunkRecord, prepare_chunks

DedupedDocs = Annotated[List[Dict[str, Any]], "deduplicated_documents"]
EmbedSummary = Annotated[Dict[str, Any], "embed_summary"]


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "yes", "on"}
    return default


def _to_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return default
    return default


def _resolve_qdrant_settings(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = config or {}
    raw_url = config.get("url") or os.getenv("QDRANT_URL") or ""
    url = raw_url.strip() or None
    host = (config.get("host") or os.getenv("QDRANT_HOST") or "").strip() or "localhost"
    port = _to_int(config.get("port") or os.getenv("QDRANT_PORT"), 6333)
    api_key_raw = config.get("api_key") or os.getenv("QDRANT_APIKEY")
    api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else api_key_raw
    if isinstance(api_key, str) and not api_key:
        api_key = None
    collection = config.get("collection") or os.getenv("COLLECTION_NAME") or "nazim_embedded"
    reset = _to_bool(config.get("reset") if "reset" in config else os.getenv("QDRANT_RESET"), False)
    batch_size = _to_int(config.get("batch_size"), 128)
    model_override = config.get("embed_model")
    return {
        "host": host,
        "port": port,
        "url": url,
        "api_key": api_key,
        "collection": collection,
        "reset": reset,
        "batch_size": batch_size,
        "embed_model": model_override,
    }


def _ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
    reset: bool,
) -> None:
    if reset:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(size=vector_size, distance=qdrant_models.Distance.COSINE),
        )
        return
    try:
        info = client.get_collection(collection_name=collection_name)
    except Exception:
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(size=vector_size, distance=qdrant_models.Distance.COSINE),
        )
        return
    params = info.config.params if info and info.config else None
    existing_size = params.vectors.size if params and params.vectors else None
    if existing_size and existing_size != vector_size:
        raise RuntimeError(
            f"Collection '{collection_name}' exists with vector size {existing_size}, "
            f"but the embedding model outputs {vector_size}. Set reset=True to recreate the collection."
        )


def _build_payload(record: ChunkRecord) -> Dict[str, Any]:
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
    return payload


@step
def embed_step(
    docs: DedupedDocs,
    qdrant_config: Optional[Dict[str, Any]] = None,
    embed_model: str = "intfloat/multilingual-e5-base",
) -> EmbedSummary:
    """Embed deduplicated documents and upsert them into Qdrant."""
    if not docs:
        return {
            "chunks": 0,
            "vectors_upserted": 0,
            "dropped_total": 0,
            "dropped_short": 0,
            "collection": None,
        }

    settings = _resolve_qdrant_settings(qdrant_config)
    model_name = settings.get("embed_model") or os.getenv("EMBED_MODEL") or embed_model
    batch_size = max(1, settings.get("batch_size", 128))

    model = SentenceTransformer(model_name)
    vector_size = model.get_sentence_embedding_dimension()

    chunks, dropped_total, dropped_short = prepare_chunks(docs)
    if not chunks:
        return {
            "chunks": 0,
            "vectors_upserted": 0,
            "dropped_total": dropped_total,
            "dropped_short": dropped_short,
            "collection": settings["collection"],
        }

    client_kwargs: Dict[str, Any] = {}
    if settings["url"]:
        client_kwargs["url"] = settings["url"]
    else:
        client_kwargs["host"] = settings["host"]
        client_kwargs["port"] = settings["port"]
    if settings["api_key"]:
        client_kwargs["api_key"] = settings["api_key"]
    client = QdrantClient(check_compatibility=False, **client_kwargs)
    _ensure_collection(client, settings["collection"], vector_size, settings["reset"])

    total_vectors = 0
    chunk_list: Sequence[ChunkRecord] = chunks

    for idx in range(0, len(chunk_list), batch_size):
        batch = chunk_list[idx : idx + batch_size]
        passages = [f"passage: {record.chunk}" for record in batch]
        embeddings = model.encode(
            passages,
            batch_size=min(32, batch_size),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        batch_points = []
        for record, embedding in zip(batch, embeddings):
            batch_points.append(
                qdrant_models.PointStruct(
                    id=record.point_id,
                    vector=embedding.tolist(),
                    payload=_build_payload(record),
                )
            )
        client.upsert(collection_name=settings["collection"], points=batch_points)
        total_vectors += len(batch_points)

    return {
        "chunks": len(chunk_list),
        "vectors_upserted": total_vectors,
        "dropped_total": dropped_total,
        "dropped_short": dropped_short,
        "collection": settings["collection"],
        "host": None if settings["url"] else settings["host"],
        "port": None if settings["url"] else settings["port"],
        "url": settings["url"],
        "model": model_name,
    }
