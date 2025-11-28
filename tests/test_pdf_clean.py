# -*- coding: utf-8 -*-
from __future__ import annotations

from src.crawler.crawlers.pdf_poems import PdfPoemsCrawler


def test_replace_cid_sequences_maps_common_codes() -> None:
    raw = "aynı(cid:3)arkıları Otuzbe(cid:250)(cid:92)(cid:213)l"
    expected = "aynı şarkıları Otuzbeşyıl"
    assert PdfPoemsCrawler._replace_cid_sequences(raw) == expected
*** End Patch
