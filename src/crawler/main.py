"""Helper entry points for running individual crawlers."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence

from dotenv import load_dotenv

from src.config.sources import load_sources_config, resolve_safe_mode, safe_mode_value, select_sources
from src.crawler.dispatcher import create_crawler
from src.etl.steps.dedup import dedupe_records
from src.etl.steps.normalize import normalize_records
from src.etl.steps.store import store_records

LOGGER = logging.getLogger(__name__)


def _resolve_mongo_url() -> str:
    mongo_url = os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
    return mongo_url or "mongodb://localhost:27017"


def _run_crawler_links(crawler, links: Sequence[str], *, user: str) -> List[Dict[str, Any]]:
    documents: List[Dict[str, Any]] = []
    for link in links:
        try:
            documents.extend(crawler.extract(link, user=user))
        except Exception as exc:  # pragma: no cover - runtime guard
            LOGGER.warning("Crawler %s failed for link %s: %s", user, link, exc)
    return documents


def run_once(source_name: str, *, use_logging: bool = True) -> int:
    if use_logging:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    load_dotenv()

    config_path = Path(__file__).resolve().parents[2] / "configs" / "sources.yaml"
    sources, top_level = load_sources_config(config_path)
    selected = select_sources(sources, [source_name])
    if not selected:
        raise KeyError(f"Source named '{source_name}' was not found in {config_path}")

    target = selected[0]
    kind = target.get("kind")
    if not kind:
        raise KeyError(f"Source '{source_name}' is missing a 'kind'")

    default_safe_mode, env_override = safe_mode_value(top_level.get("SAFE_MODE") if top_level else None)
    safe_mode = resolve_safe_mode(
        target,
        default_safe_mode=default_safe_mode,
        env_override=env_override,
        pipeline_override=None,
    )

    LOGGER.info("Running %s crawler (%s)", source_name, kind)
    crawler = create_crawler(kind, target, safe_mode=safe_mode, source_name=source_name)

    try:
        links = list(crawler.links() or [])
        if not links:
            seeds = target.get("seeds")
            if isinstance(seeds, list):
                links = [str(seed) for seed in seeds if seed]
            else:
                fallback = target.get("list_url") or target.get("url")
                if fallback:
                    links = [str(fallback)]
        documents = _run_crawler_links(crawler, links, user=source_name)
    finally:
        crawler.close()

    LOGGER.info("Collected %s raw documents for %s", len(documents), source_name)
    normalized = normalize_records(documents)
    deduped = dedupe_records(normalized)
    inserted = store_records(deduped, _resolve_mongo_url())
    LOGGER.info("%s: %s records inserted", source_name, inserted)
    return inserted


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a single Nazim Hikmet crawler source.")
    parser.add_argument("source_name", help="The 'name' field from configs/sources.yaml to execute.")
    args = parser.parse_args()
    run_once(args.source_name)
