"""Registry and factory helpers for crawler instances."""
from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple, Type

from .base import BaseCrawler

RegistryKey = Tuple[str, Optional[str]]
CRAWLER_REGISTRY: MutableMapping[RegistryKey, Type[BaseCrawler]] = {}
_DISCOVERY_DONE = False


def register_crawler(kind: str, crawler_cls: Type[BaseCrawler], *, source_name: str | None = None) -> None:
    """Register a crawler implementation for the given kind/source."""
    key = (kind, _normalize_source(source_name))
    CRAWLER_REGISTRY[key] = crawler_cls


def available_crawlers() -> Dict[str, Type[BaseCrawler]]:
    """Return a mapping of kind -> crawler class for registered defaults."""
    _ensure_discovery()
    defaults: Dict[str, Type[BaseCrawler]] = {}
    for (kind, source), crawler_cls in CRAWLER_REGISTRY.items():
        if source is None and kind not in defaults:
            defaults[kind] = crawler_cls
    return defaults


def resolve_crawler(kind: str, *, source_name: str | None = None) -> Type[BaseCrawler]:
    """Return the registered crawler class for the provided kind/source."""
    _ensure_discovery()
    key = (kind, _normalize_source(source_name))
    crawler_cls = CRAWLER_REGISTRY.get(key)
    if crawler_cls is not None:
        return crawler_cls
    fallback = CRAWLER_REGISTRY.get((kind, None))
    if fallback is None:
        raise KeyError(f"No crawler registered for kind '{kind}'.")
    return fallback


def create_crawler(
    kind: str,
    config: Mapping[str, Any],
    *,
    safe_mode: bool = False,
    source_name: str | None = None,
) -> BaseCrawler:
    """Instantiate a crawler for the given kind."""
    crawler_cls = resolve_crawler(kind, source_name=source_name)
    return crawler_cls(config, safe_mode=safe_mode)


def _normalize_source(source_name: str | None) -> str | None:
    if not source_name:
        return None
    normalized = source_name.strip().lower()
    return normalized or None


def _ensure_discovery() -> None:
    global _DISCOVERY_DONE
    if _DISCOVERY_DONE:
        return
    package = importlib.import_module("src.crawler.crawlers")
    for module in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{package.__name__}.{module.name}")
    _DISCOVERY_DONE = True

