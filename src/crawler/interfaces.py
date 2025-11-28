"""Crawler interfaces and protocols."""
from __future__ import annotations

from typing import Iterable, Protocol, Sequence, runtime_checkable


@runtime_checkable
class ICrawler(Protocol):
    """Protocol that every crawler implementation must follow."""

    kind: str

    def links(self) -> Sequence[str]:
        """Return iterable of seed URLs for crawling."""

    def extract(self, link: str, user: str, **kwargs) -> Iterable[dict]:
        """Extract payloads for a single link."""

    def close(self) -> None:
        """Release any resources held by the crawler."""
