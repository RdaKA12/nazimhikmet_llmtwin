"""ZenML pipeline orchestrating the crawl → embed ingestion flow."""
from typing import Any, Dict, Optional

from zenml import pipeline

from src.zen.steps.crawl import crawl_links, get_or_create_source
from src.zen.steps.dedup import dedup_step
from src.zen.steps.embed import embed_step
from src.zen.steps.normalize import normalize_step
from src.zen.steps.store import store_step


@pipeline
def crawl_pipeline(
    source_names: Optional[list[str]] = None,
    mongo_url: Optional[str] = None,
    mongo_db: str = "digital_twin",
    mongo_collection: str = "documents",
    qdrant_config: Optional[Dict[str, Any]] = None,
    safe_mode: Optional[bool] = None,
) -> Dict[str, Any]:
    """Run the full ingestion stack and return a summary of each stage."""
    source_payload = get_or_create_source(source_names=source_names)

    raw_documents, crawl_metadata = crawl_links(
        source_payload=source_payload,
        pipeline_safe_mode=safe_mode,
    )

    normalized_docs = normalize_step(docs=raw_documents)
    deduped_docs = dedup_step(docs=normalized_docs)

    store_summary = store_step(
        docs=deduped_docs,
        mongo_url=mongo_url,
        mongo_db=mongo_db,
        mongo_collection=mongo_collection,
    )

    embed_summary = embed_step(
        docs=deduped_docs,
        qdrant_config=qdrant_config,
    )

    return {
        "crawl": crawl_metadata,
        "store": store_summary,
        "embed": embed_summary,
    }
