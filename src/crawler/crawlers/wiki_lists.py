"""Crawlers for Wikipedia style list pages."""
from __future__ import annotations

import re
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseCrawler
from ..dispatcher import register_crawler
from ..utils.text import clean, mkhash, now, year_from_text


class WikiListCrawler(BaseCrawler):
    """Extract structured works from curated list pages."""

    kind = "poem"

    def parse(self, html: str, url: str, **_: dict) -> Iterable[dict]:
        extract = self.config.get("extract", {})
        section_css = extract.get("section_css")
        if not section_css:
            return []

        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(section_css)
        if not items:
            return []

        year_regex = extract.get("year_regex")
        year_pattern = re.compile(year_regex) if year_regex else None

        documents: List[dict] = []
        for li in items:
            title = clean(li.get_text(separator=" "))
            if not title:
                continue
            year = None
            if year_pattern:
                match = year_pattern.search(title)
                if match:
                    year = int(match.group(0))
            if year is None:
                year = year_from_text(title)
            link_el = li.select_one("a[href]")
            detail_url = urljoin(self.config.get("base", url), link_el.get("href")) if link_el else url

            document = {
                "type": self.kind,
                "work_type": self.kind,
                "lang": "tr",
                "author": "Nazim Hikmet",
                "title": title,
                "text_full": "",
                "summary": "",
                "year": year,
                "collection": None,
                "source_url": detail_url,
                "source_name": self.config.get("base", ""),
                "license": "unknown",
                "hash": mkhash(detail_url, title),
                "created_at": now(),
            }
            documents.append(document)
        return documents


class BooksCrawler(WikiListCrawler):
    """Proxy crawler for book lists."""

    kind = "book"


class PlaysCrawler(WikiListCrawler):
    """Proxy crawler for play lists."""

    kind = "play"


class NovelsCrawler(WikiListCrawler):
    """Proxy crawler for novel lists."""

    kind = "novel"


register_crawler(WikiListCrawler.kind, WikiListCrawler)
register_crawler(BooksCrawler.kind, BooksCrawler)
register_crawler(PlaysCrawler.kind, PlaysCrawler)
register_crawler(NovelsCrawler.kind, NovelsCrawler)
