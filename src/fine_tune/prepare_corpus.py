from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from bs4 import BeautifulSoup
from dotenv import load_dotenv


CONTENT_KEYS: tuple[str, ...] = (
    "content",
    "text",
    "text_full",
    "body",
    "full_text",
    "text_body",
    "raw_text",
)


def _resolve_first_str(data: Dict[str, Any], keys: Iterable[str]) -> str:
    for k in keys:
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _clean_text(raw: str) -> str:
    soup = BeautifulSoup(raw or "", "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_documents(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("documents", "items", "data"):
            items = data.get(key)
            if isinstance(items, list):
                return items
    raise ValueError("Unsupported JSON structure for documents")


def write_lines(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            if not line:
                continue
            f.write(line.rstrip() + "\n")


def split_train_val(lines: List[str], val_ratio: float = 0.02) -> Tuple[List[str], List[str]]:
    if not lines:
        return [], []
    n_val = max(1, int(len(lines) * val_ratio))
    return lines[n_val:], lines[:n_val]


def main() -> None:
    load_dotenv()
    input_path = Path(os.getenv("INPUT_JSON", "digital_twin.documents.json")).resolve()
    out_dir = Path(os.getenv("CORPUS_DIR", "data/corpus")).resolve()

    if not input_path.exists():
        raise SystemExit(f"Input JSON not found: {input_path}")

    docs = load_documents(input_path)

    lines: List[str] = []
    for doc in docs:
        raw = _resolve_first_str(doc, CONTENT_KEYS)
        if not raw:
            continue
        cleaned = _clean_text(raw)
        # Çok kısa parçaları atla
        if len(cleaned) < 80:
            continue
        lines.append(cleaned)

    if not lines:
        raise SystemExit("No valid lines extracted from documents")

    train, val = split_train_val(lines)

    write_lines(out_dir / "corpus.txt", lines)
    write_lines(out_dir / "train.txt", train)
    write_lines(out_dir / "val.txt", val)

    print(
        "\nCorpus prepared:\n"
        f"  documents: {len(docs)}\n"
        f"  usable_lines: {len(lines)}\n"
        f"  train: {len(train)} | val: {len(val)}\n"
        f"  dir: {out_dir}\n"
    )


if __name__ == "__main__":
    main()

