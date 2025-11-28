from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from src.llm.providers import load_provider
from src.rag.prompt import build_nazim_prompt_tr
from src.rag.retriever import retrieve


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_eval(eval_path: Path) -> Path:
    load_dotenv()
    cases = read_jsonl(eval_path)
    provider = load_provider()

    results: List[Dict[str, Any]] = []
    for i, case in enumerate(cases, start=1):
        prompt = str(case.get("prompt") or case.get("question") or "").strip()
        if not prompt:
            continue
        contexts = retrieve(prompt, top_k=int(case.get("k", 5)), kinds=None, language="tr")
        full_prompt = build_nazim_prompt_tr(prompt, contexts)
        answer = provider.generate(full_prompt, max_tokens=int(case.get("max_tokens", 512)))
        results.append(
            {
                "idx": i,
                "prompt": prompt,
                "answer": answer,
                "contexts": [
                    {
                        "title": c.get("title"),
                        "source": c.get("source") or c.get("source_url"),
                        "kind": c.get("kind"),
                        "author": c.get("author"),
                        "score": c.get("_score"),
                    }
                    for c in contexts
                ],
                "reference": case.get("reference"),
                "meta": {k: v for k, v in case.items() if k not in {"prompt", "question", "reference"}},
            }
        )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("outputs") / "eval" / eval_path.stem / ts
    out_path = out_dir / "results.jsonl"
    write_jsonl(out_path, results)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run simple batch eval over JSONL prompts.")
    parser.add_argument("file", help="Path to JSONL eval set.")
    args = parser.parse_args()

    eval_path = Path(args.file)
    if not eval_path.exists():
        raise SystemExit(f"Eval file not found: {eval_path}")

    out = run_eval(eval_path)
    print(f"Saved results to: {out}")


if __name__ == "__main__":
    main()

