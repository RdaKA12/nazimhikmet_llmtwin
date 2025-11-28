"""HTTP utilities for fetching pages with retry and backoff."""
from __future__ import annotations

import logging
import time

import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


class FetchError(RuntimeError):
    """Raised when fetching a URL fails after retries."""


def http_get(url: str, timeout: int = 20) -> str:
    """Perform a single HTTP GET request with default crawler headers."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    if not response.encoding:
        response.encoding = response.apparent_encoding
    return response.text


def fetch_url(url: str, *, timeout: int = 30, retries: int = 3, backoff: float = 1.5) -> str:
    """Fetch a URL with exponential backoff on retryable status codes."""
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            return http_get(url, timeout=timeout)
        except requests.RequestException as exc:
            LOGGER.warning("Attempt %s/%s failed for %s: %s", attempt, retries, url, exc)
            if attempt >= retries:
                raise FetchError(f"Failed to fetch {url}") from exc
            sleep_for = backoff ** attempt
            time.sleep(sleep_for)
    raise FetchError(f"Exhausted retries for {url}")
