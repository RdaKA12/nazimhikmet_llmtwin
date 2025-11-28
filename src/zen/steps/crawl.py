"""ZenML steps for resolving sources and crawling content."""

import logging
from typing import Any, Dict, List, Mapping, Sequence

from zenml import step

from src.config.sources import load_sources_config, resolve_safe_mode, safe_mode_value, select_sources
from src.crawler.dispatcher import create_crawler

logger = logging.getLogger(__name__)

@step
def get_or_create_source(
    config_path: str = "configs/sources.yaml",
    source_names: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Load source definitions and return the subset requested by the pipeline."""
    sources, top_level = load_sources_config(config_path)
    selected_sources = select_sources(sources, source_names)
    default_safe_mode, env_override = safe_mode_value(top_level.get("SAFE_MODE") if top_level else None)
    return {
        "sources": selected_sources,
        "default_safe_mode": default_safe_mode,
        "env_override": env_override,
    }


def _links_for_crawler(crawler) -> Sequence[str]:
    try:
        links = crawler.links()
    except AttributeError:
        return []
    return list(links)


@step
def crawl_links(
    source_payload: Dict[str, Any],
    pipeline_safe_mode: bool | None = None,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Execute registered crawlers for the provided sources and return raw payloads."""
    sources: List[Dict[str, Any]] = list(source_payload.get("sources", []))
    documents: List[Dict[str, Any]] = []
    summary: List[Dict[str, Any]] = []

    for source in sources:
        name = source.get("name") or source.get("kind") or "<unknown>"
        if not source.get("enabled", True):
            summary.append({"name": name, "kind": source.get("kind"), "enabled": False, "documents": 0})
            continue

        kind = source.get("kind")
        if not kind:
            summary.append({"name": name, "error": "Missing 'kind' attribute", "documents": 0})
            continue

        default_safe = bool(source_payload.get("default_safe_mode"))
        env_override = bool(source_payload.get("env_override"))
        safe_mode = resolve_safe_mode(
            source,
            default_safe_mode=default_safe,
            env_override=env_override,
            pipeline_override=pipeline_safe_mode,
        )
        try:
            crawler = create_crawler(kind, source, safe_mode=safe_mode, source_name=name)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to instantiate crawler for %s (%s)", name, kind)
            summary.append({"name": name, "kind": kind, "error": str(exc), "documents": 0})
            continue

        errors: List[str] = []
        extracted_total = 0
        links = _links_for_crawler(crawler) or list(source.get("seeds", []))
        if not links:
            fallback = source.get("list_url") or source.get("url")
            if fallback:
                links = [fallback]

        try:
            for link in links:
                try:
                    payloads = crawler.extract(link, user=name or "crawler")
                except Exception as exc:  # pragma: no cover - runtime guard
                    logger.warning("Crawler %s failed for link %s: %s", name, link, exc)
                    errors.append(f"{link}: {exc}")
                    continue
                documents.extend(payloads)
                extracted_total += len(payloads)
        finally:
            try:
                crawler.close()
            except Exception:  # pragma: no cover - defensive cleanup
                logger.debug("Crawler %s raised during close()", name, exc_info=True)

        summary.append(
            {
                "name": name,
                "kind": kind,
                "safe_mode": safe_mode,
                "links_processed": len(links),
                "documents": extracted_total,
                "errors": errors,
            }
        )

    metadata: Dict[str, Any] = {
        "total_sources": len(summary),
        "total_documents": len(documents),
        "sources": summary,
    }
    return documents, metadata
