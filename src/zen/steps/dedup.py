"""Deduplication step delegating to the ETL layer."""
from typing import Any, Dict, List

from typing_extensions import Annotated
from zenml import step

from src.etl.steps.dedup import dedupe_records

NormalizedDocs = Annotated[List[Dict[str, Any]], "normalized_documents"]
DedupedDocs = Annotated[List[Dict[str, Any]], "deduplicated_documents"]


@step
def dedup_step(docs: NormalizedDocs) -> DedupedDocs:
    """Remove duplicates using the shared ETL deduplication logic."""
    return dedupe_records(docs)
