"""Base crawler abstractions for Nazim twin ingestion."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .utils.fetch import http_get


class BaseCrawler(ABC):
    """Shared behaviour for HTTP-based crawlers."""

    kind: str = "base"
    backoff_base: float = 1.0
    backoff_factor: float = 2.0
    max_retries: int = 3

    def __init__(self, config: Mapping[str, Any], *, safe_mode: bool = False) -> None:
        self.config = dict(config)
        self.safe_mode = safe_mode
        self.logger = logging.getLogger(self.__class__.__name__)
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )

    def links(self) -> Sequence[str]:
        """Return candidate links (seeds) configured for the crawler."""
        seeds = self.config.get("seeds")
        if isinstance(seeds, (list, tuple, set, frozenset)):
            links = [str(seed) for seed in seeds if seed]
            if links:
                return links
        fallback = self.config.get("list_url") or self.config.get("url") or self.config.get("base")
        return [str(fallback)] if fallback else []

    def extract(self, link: str, user: str, **kwargs: Any) -> List[dict]:
        """Fetch `link`, parse its contents, and return prepared payloads."""
        html = self.fetch(link)
        documents: List[dict] = []
        for record in self.parse(html, link, **kwargs):
            payload = self._finalize_payload(record, link=link, user=user)
            documents.append(payload)
        return documents

    def fetch(self, url: str) -> str:
        """Fetch a page using the shared HTTP helper with retries."""
        attempt = 0
        while attempt < self.max_retries:
            try:
                self.logger.debug("Fetching %s", url)
                return http_get(url)
            except Exception as exc:  # pragma: no cover - defensive logging
                attempt += 1
                wait_time = self.backoff_base * (self.backoff_factor ** (attempt - 1))
                self.logger.warning(
                    "Fetch failed for %s (attempt %s/%s): %s",
                    url,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt >= self.max_retries:
                    raise
                time.sleep(wait_time)
        raise RuntimeError("Fetch retries exhausted")

    @abstractmethod
    def parse(self, html: str, url: str, **kwargs: Any) -> Iterable[dict]:
        """Parse the fetched HTML into structured data dictionaries."""

    def close(self) -> None:
        """Release any external resources held by the crawler."""

    def _finalize_payload(self, record: dict, *, link: str, user: str) -> dict:
        payload = dict(record)
        payload.setdefault("kind", self.kind)
        payload.setdefault("source_url", payload.get("source_url") or link)
        if user:
            payload.setdefault("source_name", user)
        payload.setdefault("safe_mode", bool(self.safe_mode))
        return self._apply_safe_mode(payload)

    def _apply_safe_mode(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.safe_mode:
            return payload
        item = dict(payload)
        text_full = item.get("text_full")
        if text_full:
            excerpt = text_full[:250]
            item["summary"] = excerpt
            item["text_full"] = ""
        return item


class BaseSeleniumCrawler(BaseCrawler):
    """Crawler variant that sources content via Selenium WebDriver."""

    def __init__(self, config: Mapping[str, Any], *, safe_mode: bool = False) -> None:
        super().__init__(config, safe_mode=safe_mode)
        self._driver = None

    def fetch(self, url: str) -> str:  # type: ignore[override]
        driver = self._ensure_driver()
        driver.get(url)
        return driver.page_source

    def close(self) -> None:  # type: ignore[override]
        driver = self._driver
        if driver is not None:
            try:
                driver.quit()
            finally:
                self._driver = None

    def _ensure_driver(self):
        if self._driver is None:
            self._driver = self.build_driver()
        return self._driver

    @abstractmethod
    def build_driver(self):
        """Construct the WebDriver instance."""
