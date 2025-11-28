"""Tests for the ad-hoc scraper module that avoid real HTTP calls."""

from __future__ import annotations

from typing import Callable

import pytest

import test_scraper


class MockResponse:
    """Simple object mimicking ``requests.Response`` for our tests."""

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:  # pragma: no cover - behaviourless stub
        return None


def build_mock_get(response_text: str) -> Callable[..., MockResponse]:
    """Create a ``requests.get`` replacement that returns the given HTML."""

    def _mock_get(url: str, *, headers: dict[str, str], timeout: int) -> MockResponse:
        assert url == test_scraper.URL
        assert headers is test_scraper.HEADERS
        assert timeout == 20
        return MockResponse(response_text)

    return _mock_get


def test_fetch_poem_parses_title_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <html>
        <body>
            <h1 class="entry-title">Sample Title</h1>
            <div class="entry-content">Line one<br/>Line two</div>
        </body>
    </html>
    """
    monkeypatch.setattr(test_scraper.requests, "get", build_mock_get(html))

    title, body = test_scraper.fetch_poem()

    assert title == "Sample Title"
    assert body.replace("\n", "").startswith("Line one")


def test_main_prints_summary(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    body_text = "A" * 600
    html = f"""
    <html>
        <body>
            <h1 class='entry-title'>Mock Title</h1>
            <div class='entry-content'>{body_text}</div>
        </body>
    </html>
    """
    monkeypatch.setattr(test_scraper.requests, "get", build_mock_get(html))

    test_scraper.main()

    captured = capsys.readouterr()
    assert "Title: Mock Title" in captured.out
    # Only the first 500 characters should be printed.
    assert f"Body snippet: {body_text[:500]}" in captured.out
