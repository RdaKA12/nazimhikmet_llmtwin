"""Crawler that collects news articles about Nazim Hikmet."""
from __future__ import annotations

from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..base import BaseCrawler
from ..dispatcher import register_crawler
from ..utils.text import clean, mkhash, now


class NewsCrawler(BaseCrawler):
    """Extracts news metadata and full text from archive pages."""

    kind = "news"

    def parse(self, html: str, url: str, **_: dict) -> Iterable[dict]:
        extract = self.config.get("extract", {})
        fields = extract.get("fields", {})
        card_css = extract.get("card_css")
        if not (card_css and fields):
            return []

        soup = BeautifulSoup(html, "html.parser")
        documents: List[dict] = []

        for card in soup.select(card_css):
            title_el = card.select_one(fields.get("title_css")) if fields.get("title_css") else None
            url_el = card.select_one(fields.get("url_attr")) if fields.get("url_attr") else None
            date_el = card.select_one(fields.get("date_css")) if fields.get("date_css") else None

            title = clean(title_el.get_text(separator=" ")) if title_el else ""
            href = url_el.get("href") if url_el else None
            date_text = clean(date_el.get("datetime", "") or date_el.get_text()) if date_el else ""
            if not href:
                continue
            detail_url = urljoin(self.config.get("base", url), href)
            try:
                detail_html = self.fetch(detail_url)
            except Exception:  # pragma: no cover - network failure path
                self.logger.warning("Skipping news page %s", detail_url)
                continue
            body = self._parse_body(detail_html, fields)
            if not body:
                continue

            document = {
                "type": "news",
                "work_type": None,
                "lang": "tr",
                "author": "Nazim Hikmet",
                "title": title,
                "text_full": body,
                "summary": "",
                "collection": extract.get("collection"),
                "date": date_text,
                "source_url": detail_url,
                "source_name": self.config.get("base", ""),
                "license": "unknown",
                "hash": mkhash(detail_url, title, body),
                "created_at": now(),
            }
            documents.append(document)
        return documents

    def _parse_body(self, html: str, fields: dict) -> str:
        soup = BeautifulSoup(html, "html.parser")
        full_css = fields.get("full_css")
        if not full_css:
            return ""
        body_elements = soup.select(full_css)
        text = "\n\n".join(clean(el.get_text("\n")) for el in body_elements)
        return text


register_crawler(NewsCrawler.kind, NewsCrawler)
