"""Tests for the FastAPI application endpoints."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.app import ingest_test


def test_ingest_test_respects_safe_mode(monkeypatch) -> None:
    captured: Dict[str, Any] = {}

    monkeypatch.delenv("SAFE_MODE", raising=False)

    class DummyCrawler:
        def __init__(self, config: Dict[str, Any], safe_mode: bool = False) -> None:
            captured["config"] = config
            captured["safe_mode"] = safe_mode

        def run(self) -> List[Dict[str, Any]]:
            return [
                {
                    "title": "Test Poem",
                    "text_full": "The quick brown fox jumps over the lazy dog.",
                    "summary": "",
                }
            ]

    monkeypatch.setattr("src.api.app.PoemPageCrawler", DummyCrawler)

    body = ingest_test(url="https://example.com/poem")

    assert captured["safe_mode"] is False
    assert body["preview"][0]["text_full"] == "The quick brown fox jumps over the lazy dog."
    assert body["preview"][0]["summary"] == ""
