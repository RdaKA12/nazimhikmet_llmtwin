"""Basic smoke tests for configuration and utilities."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.sources import load_sources_config
from src.crawler.dispatcher import available_crawlers
from src.crawler.utils.text import year_from_text


def test_sources_yaml_exists() -> None:
    config_path = PROJECT_ROOT / "configs" / "sources.yaml"
    sources, _ = load_sources_config(config_path)
    assert isinstance(sources, list)
    assert sources


def test_kind2mod_mapping() -> None:
    registry = available_crawlers()
    for kind in ["poem_page", "poem", "play", "book", "novel", "news", "pdf_poems"]:
        assert kind in registry


def test_year_from_text() -> None:
    assert year_from_text("Nazim Hikmet 1935'te yazdi") == 1935
    assert year_from_text("Yil 2001, hatirliyorum") == 2001
    assert year_from_text("Hic yil yok") is None
