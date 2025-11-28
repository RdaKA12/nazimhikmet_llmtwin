"""Crawlers that collect full poem texts from manually curated sources."""
from __future__ import annotations

import re
from typing import Iterable, List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..base import BaseCrawler
from ..dispatcher import register_crawler
from ..utils.text import canonicalize, clean, mkhash, now

SITE_TITLE_SUFFIX_RE = re.compile(
    r"\s*(?:[-\u2013\u2014|]\s*)?(?:\u015eiir Ar\u015fivi|Siir Ar\u015fivi|\u015eiir Sitesi|Siir Sitesi)\s*$",
    re.IGNORECASE,
)


class PoemPageCrawler(BaseCrawler):
    """Crawler that downloads full poem texts from detail pages."""

    kind = "poem_page"

    def parse(self, html: str, url: str, **_: dict) -> Iterable[dict]:
        extract = self.config.get("extract", {})
        if extract.get("index_card_css") and extract.get("detail_link_css"):
            return self._parse_index(html, url, extract)
        return self._parse_detail(html, url, extract)

    def _parse_index(self, html: str, url: str, extract: dict) -> List[dict]:
        documents: List[dict] = []
        paging = self.config.get("paging", {})
        max_pages = paging.get("max_pages", 1)
        next_selector = paging.get("next_css")

        page_url = url
        page_html = html
        processed_pages = 0
        visited = set()

        seen_detail_urls = set()

        while page_html and processed_pages < max_pages:
            processed_pages += 1
            visited.add(page_url)
            soup = BeautifulSoup(page_html, "html.parser")
            cards = soup.select(extract["index_card_css"])
            self.logger.info("DEBUG index cards: %d at %s", len(cards), page_url)
            for card in cards:
                link_el = card.select_one(extract["detail_link_css"])
                if not link_el:
                    continue
                href = link_el.get("href")
                if not href:
                    continue
                detail_url = urljoin(self.config.get("base", page_url), href)
                normalized_detail_url = detail_url.rstrip("/")
                if normalized_detail_url in seen_detail_urls:
                    continue
                seen_detail_urls.add(normalized_detail_url)
                try:
                    detail_html = self.fetch(detail_url)
                except Exception:  # pragma: no cover - network failure path
                    self.logger.warning("Skipping detail page %s", detail_url)
                    continue
                documents.extend(self._parse_detail(detail_html, detail_url, extract))

            if not next_selector:
                break
            next_el = soup.select_one(next_selector)
            if not next_el:
                break
            href = next_el.get("href")
            if not href:
                break
            next_url = urljoin(self.config.get("base", page_url), href)
            if next_url in visited:
                break
            try:
                page_html = self.fetch(next_url)
            except Exception:  # pragma: no cover - network failure path
                self.logger.warning("Failed to fetch next page %s", next_url)
                break
            page_url = next_url
        return documents

    def _parse_detail(self, html: str, url: str, extract: dict) -> List[dict]:
        soup = BeautifulSoup(html, "html.parser")
        title_css = extract.get("title_css")
        full_css = extract.get("full_css")
        if not (title_css and full_css):
            self.logger.warning("Missing title/full CSS selectors for %s", self.config.get("name"))
            return []

        title_el = soup.select_one(title_css) if title_css else None
        raw_title = title_el.get_text(" ") if title_el else ""
        title = clean(raw_title)

        if not title:
            og = soup.select_one("meta[property='og:title']")
            if og and og.get("content"):
                title = clean(og.get("content"))

        if not title:
            title_tag = soup.select_one("title")
            if title_tag:
                title = clean(title_tag.get_text(" "))

        if title:
            title = SITE_TITLE_SUFFIX_RE.sub("", title).strip()

        if not title:
            slug = urlparse(url).path.rstrip("/").split("/")[-1]
            if slug:
                title = clean(slug.replace("-", " "))

        if not title:
            return []

        blocks = []
        for el in soup.select(full_css):
            text = clean(el.get_text("\n"))
            if text:
                blocks.append(text)

        if not blocks:
            container = soup.select_one("div.entry-content, article")
            if container:
                for bad in container.select(
                    "script,style,nav,header,footer,aside,.sharedaddy,.share,[class*='share'],.post-meta,.postmeta,.cat-links,.tags,.entry-footer,.comments,.wp-block-buttons,.stream-item,ins.adsbygoogle,.adsbygoogle,iframe"
                ):
                    bad.decompose()
                fallback_text = clean(container.get_text("\n"))
                if fallback_text:
                    blocks.append(fallback_text)

        text_full = "\n\n".join(blocks).strip()
        if not text_full:
            return []

        author = self.config.get("author", "Naz\u0131m Hikmet")
        author_canon = canonicalize(author)
        lines = text_full.splitlines()
        if lines and canonicalize(lines[0]) == author_canon:
            remainder = "\n".join(lines[1:]).strip()
            if remainder:
                text_full = remainder

        doc_hash = mkhash(
            canonicalize(author),
            canonicalize(title),
            canonicalize(text_full),
        )

        self.logger.info("DEBUG title=%r text_len=%d url=%s", title, len(text_full), url)

        document = {
            "type": "poem",
            "work_type": self.config.get("work_type", "poem"),
            "lang": "tr",
            "author": author,
            "title": title,
            "text_full": text_full,
            "summary": "",
            "collection": self.config.get("extract", {}).get("collection"),
            "source_url": url,
            "source_name": self.config.get("base", ""),
            "license": "unknown",
            "hash": doc_hash,
            "created_at": now(),
        }
        return [document]


register_crawler(PoemPageCrawler.kind, PoemPageCrawler)


