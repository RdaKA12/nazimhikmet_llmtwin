"""Utilities for loading and filtering crawler source configurations."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import yaml


def load_sources_config(config_path: str | Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load the YAML configuration and return (sources, top_level_config)."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Source configuration not found at {config_path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if isinstance(data, list):
        return list(data), {}
    if isinstance(data, dict):
        sources = data.get("sources", [])
        if not isinstance(sources, list):
            raise TypeError("`sources` section must be a list of source definitions.")
        return list(sources), data
    raise TypeError("sources.yaml must define either a list or a mapping with a 'sources' key.")


def select_sources(
    sources: Iterable[Dict[str, Any]],
    source_names: Sequence[str] | None,
) -> List[Dict[str, Any]]:
    """Filter sources by name if provided, erroring when names are missing."""
    if not source_names:
        return list(sources)
    requested = {name.strip() for name in source_names if name and name.strip()}
    selected = [source for source in sources if source.get("name") in requested]
    missing = requested.difference({source.get("name") for source in selected})
    if missing:
        raise KeyError(f"Sources not found in configuration: {', '.join(sorted(missing))}")
    return selected


def safe_mode_value(config_value: bool | None) -> Tuple[bool, bool]:
    """Resolve SAFE_MODE setting prioritising environment variables."""
    env_value = os.getenv("SAFE_MODE")
    if env_value is not None:
        return env_value.lower() in {"1", "true", "yes", "on"}, True
    return bool(config_value), False


def resolve_safe_mode(
    source: Mapping[str, Any],
    *,
    default_safe_mode: bool,
    env_override: bool,
    pipeline_override: bool | None = None,
) -> bool:
    """Compute the effective safe mode value for a source."""
    if env_override:
        return default_safe_mode
    if pipeline_override is not None:
        return pipeline_override
    return bool(source.get("safe_mode", default_safe_mode))
