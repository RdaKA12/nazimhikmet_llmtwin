"""Normalization step wrapping the ETL implementation."""
from typing import Any, Dict, List

from typing_extensions import Annotated
from zenml import step

from src.etl.steps.normalize import normalize_records

RawDocs = Annotated[List[Dict[str, Any]], "raw_documents"]
NormalizedDocs = Annotated[List[Dict[str, Any]], "normalized_documents"]


@step
def normalize_step(docs: RawDocs) -> NormalizedDocs:
    """Apply shared normalization logic to crawler outputs."""
    return normalize_records(docs)
