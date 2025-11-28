import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pymongo import ASCENDING, MongoClient

from src.crawler.utils.text import canonicalize, clean, mkhash

MONGO = "mongodb://mongo:27017"
DB = "digital_twin"
SOURCES = {"https://siirarsivi.net", "https://siir.sitesi.web.tr", "https://secmehikayeler.com"}
UA = {"User-Agent": "Mozilla/5.0"}

SITE_SUFFIX_RE = re.compile(
    r"\s*(?:[-\u2013\u2014|]\s*)?(?:\u015eiir Ar\u015fivi|Siir Ar\u015fivi|\u015eiir Sitesi|Siir Sitesi)\s*$",
    re.IGNORECASE,
)


def smart_title_from_page(url: str) -> str:
    try:
        html = requests.get(url, headers=UA, timeout=20).text
    except Exception:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    og = soup.select_one("meta[property='og:title']")
    if og and og.get("content"):
        title = clean(og.get("content"))
    if not title:
        title_tag = soup.select_one("title")
        if title_tag:
            title = clean(title_tag.get_text(" "))
    if title:
        title = SITE_SUFFIX_RE.sub("", title).strip()
        return title
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return clean(slug.replace("-", " "))


def main() -> None:
    client = MongoClient(MONGO)
    collection = client[DB]["documents"]

    try:
        collection.create_index([("hash", ASCENDING)], unique=True, sparse=True, name="uniq_hash")
    except Exception:
        pass

    cursor = collection.find({"source_name": {"$in": list(SOURCES)}})
    updated = 0

    for doc in cursor:
        title = doc.get("title") or ""
        text_full = doc.get("text_full") or ""
        url = doc.get("source_url") or ""
        author = doc.get("author") or "Naz\u0131m Hikmet"

        if not title and url:
            title = smart_title_from_page(url)

        new_hash = mkhash(
            canonicalize(author),
            canonicalize(title),
            canonicalize(text_full),
        )

        updates = {}
        if title and doc.get("title") != title:
            updates["title"] = title
        if doc.get("hash") != new_hash:
            updates["hash"] = new_hash

        if updates:
            collection.update_one({"_id": doc["_id"]}, {"$set": updates})
            updated += 1

    print(f"updated docs: {updated}")


if __name__ == "__main__":
    main()

