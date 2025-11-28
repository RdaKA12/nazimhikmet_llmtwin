"""Quick CLI helper to query the Nazim embedding collection."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query the Nazim embedding collection via Qdrant."
    )
    parser.add_argument("query", help="Search phrase, e.g. \"Nazim'in umut temasi\"")
    return parser.parse_args(argv)


def main(argv: List[str]) -> None:
    args = parse_args(argv)

    load_dotenv()

    model_name = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-base")
    collection_name = os.getenv("COLLECTION_NAME", "nazim_embedded")
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    api_key = os.getenv("QDRANT_APIKEY") or None

    model = SentenceTransformer(model_name)
    query_vector = model.encode(
        f"query: {args.query}",
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    client = QdrantClient(host=host, port=port, api_key=api_key)
    try:
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector.tolist(),
            limit=5,
            with_payload=True,
        )
    except Exception as exc:  # noqa: BLE001 - surface Qdrant errors to the CLI
        print(f"[ERROR] Qdrant search failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No matches found.")
        return

    print(f"Top 5 results for query: {args.query!r}\n")
    for rank, point in enumerate(results, start=1):
        payload = point.payload or {}
        title = payload.get("title", "Unknown title")
        kind = payload.get("kind", "unknown")
        source = payload.get("source", "unknown")
        distance = point.score
        print(f"{rank}. {title} | kind: {kind} | source: {source} | distance: {distance:.4f}")


if __name__ == "__main__":
    main(sys.argv[1:])
