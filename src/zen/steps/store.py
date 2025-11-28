"""ZenML store step delegating to the shared ETL implementation."""
import os
from typing import Any, Dict, List, Optional

from typing_extensions import Annotated
from zenml import step

from src.etl.steps.store import store_records

DedupedDocs = Annotated[List[Dict[str, Any]], "deduplicated_documents"]
StoreSummary = Annotated[Dict[str, Any], "store_summary"]


@step
def store_step(
    docs: DedupedDocs,
    mongo_url: Optional[str] = None,
    mongo_db: str = "digital_twin",
    mongo_collection: str = "documents",
) -> StoreSummary:
    """Validate and persist records to MongoDB."""
    effective_url = mongo_url or os.getenv("MONGO_URL") or "mongodb://localhost:27017"
    inserted = store_records(docs, effective_url, db_name=mongo_db, collection=mongo_collection)
    return {
        "inserted": inserted,
        "database": mongo_db,
        "collection": mongo_collection,
        "mongo_url": effective_url,
    }
