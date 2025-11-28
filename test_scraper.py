"""Utilities for scraping a single poem page for debugging purposes."""

from __future__ import annotations

import requests
import bs4

URL = "https://siirarsivi.net/3037/ben-senden-once-olmek-isterim/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_poem(url: str = URL, headers: dict[str, str] = HEADERS) -> tuple[str | None, str | None]:
    """Retrieve the poem title and body text from the given URL."""

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    try:
        soup = bs4.BeautifulSoup(response.text, "lxml")
    except bs4.FeatureNotFound:  # pragma: no cover - depends on optional parser
        soup = bs4.BeautifulSoup(response.text, "html.parser")
    title = soup.select_one("h1.entry-title, h1.post-title, h1")
    body = soup.select_one(
        "div.entry-content, article .entry-content, article .post-content, article"
    )

    title_text = title.text.strip() if title else None
    body_text = body.text if body else None
    return title_text, body_text


def main() -> None:
    """Fetch the poem and print a short summary for manual inspection."""

    title, body = fetch_poem()
    print("Title:", title)
    print("Body snippet:", body[:500] if body else None)


if __name__ == "__main__":
    main()
