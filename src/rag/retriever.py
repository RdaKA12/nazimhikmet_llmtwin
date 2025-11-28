from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer


def _get_qdrant_client() -> Tuple[QdrantClient, str]:
    host = os.getenv("QDRANT_HOST")
    port = os.getenv("QDRANT_PORT")
    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_APIKEY") or None

    collection = (
        os.getenv("COLLECTION_NAME")
        or os.getenv("QDRANT_COLLECTION")
        or "nazim_embedded"
    )

    if url:
        client = QdrantClient(url=url, api_key=api_key, check_compatibility=False)
    else:
        client = QdrantClient(host=host or "localhost", port=int(port or 6333), api_key=api_key, check_compatibility=False)
    return client, collection


_EMBED_MODEL: SentenceTransformer | None = None
_EMBED_ERROR: str | None = None


def _get_embedder() -> SentenceTransformer | None:
    global _EMBED_MODEL, _EMBED_ERROR
    if _EMBED_MODEL is None and _EMBED_ERROR is None:
        try:
            name = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")
            _EMBED_MODEL = SentenceTransformer(name)
        except Exception as exc:  # noqa: BLE001
            _EMBED_ERROR = f"embedding runtime unavailable: {exc}"
            return None
    return _EMBED_MODEL


def embed_query(text: str) -> List[float] | None:
    model = _get_embedder()
    if model is None:
        return None
    # e5-style prefix for query embeddings
    vec = model.encode([f"query: {text}"], normalize_embeddings=True)[0]
    return vec.tolist()  # type: ignore[no-any-return]


def _build_filter(filter_kinds: Optional[List[str]] = None, filter_lang: Optional[str] = None) -> Optional[qmodels.Filter]:
    clauses: List[qmodels.Condition] = []
    if filter_kinds:
        clauses.append(
            qmodels.FieldCondition(
                key="kind",
                match=qmodels.MatchAny(any=filter_kinds),
            )
        )
    if filter_lang:
        should_lang: List[qmodels.Condition] = [
            qmodels.FieldCondition(key="language", match=qmodels.MatchValue(value=filter_lang)),
            qmodels.FieldCondition(key="lang", match=qmodels.MatchValue(value=filter_lang)),
        ]
        clauses.append(qmodels.Filter(should=should_lang))
    if not clauses:
        return None
    must: List[qmodels.Condition] = []
    for c in clauses:
        if isinstance(c, qmodels.Filter):
            must.append(c)
        else:
            must.append(c)
    return qmodels.Filter(must=must)


def retrieve(
    query: str,
    top_k: int = 5,
    *,
    kinds: Optional[List[str]] = None,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search Qdrant by embedding the query and returning payloads with scores."""
    client, collection = _get_qdrant_client()
    vector = embed_query(query)
    if vector is None:
        return []

    try:
        res = client.search(
            collection_name=collection,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
            score_threshold=None,
            query_filter=_build_filter(kinds, language),
        )
    except Exception:
        # Gracefully degrade if Qdrant is unreachable or the collection is missing
        return []
    out: List[Dict[str, Any]] = []
    for point in res:
        payload = dict(point.payload or {})
        payload["_score"] = float(point.score or 0.0)
        out.append(payload)
    return out
