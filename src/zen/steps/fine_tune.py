from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from typing_extensions import Annotated
from zenml import step

from src.fine_tune import prepare_corpus as prepare_corpus_module
from src.fine_tune import train_cpt as train_cpt_module

CorpusSummary = Annotated[Dict[str, Any], "corpus_summary"]
TrainSummary = Annotated[Dict[str, Any], "train_summary"]


@step
def prepare_corpus_step(
    input_json: Optional[str] = None,
    corpus_dir: Optional[str] = None,
) -> CorpusSummary:
    """Prepare plain-text corpus for continued pretraining (CPT)."""
    load_dotenv()

    if input_json is not None:
        os.environ["INPUT_JSON"] = input_json
    if corpus_dir is not None:
        os.environ["CORPUS_DIR"] = corpus_dir

    input_path = Path(os.getenv("INPUT_JSON", "digital_twin.documents.json")).resolve()
    out_dir = Path(os.getenv("CORPUS_DIR", "data/corpus")).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input JSON not found: {input_path}")

    docs = prepare_corpus_module.load_documents(input_path)

    lines = []
    for doc in docs:
        raw = prepare_corpus_module._resolve_first_str(doc, prepare_corpus_module.CONTENT_KEYS)
        if not raw:
            continue
        cleaned = prepare_corpus_module._clean_text(raw)
        if len(cleaned) < 80:
            continue
        lines.append(cleaned)

    if not lines:
        raise RuntimeError("No valid lines extracted from documents for corpus.")

    train, val = prepare_corpus_module.split_train_val(lines)

    prepare_corpus_module.write_lines(out_dir / "corpus.txt", lines)
    prepare_corpus_module.write_lines(out_dir / "train.txt", train)
    prepare_corpus_module.write_lines(out_dir / "val.txt", val)

    return {
        "input_path": str(input_path),
        "output_dir": str(out_dir),
        "documents": len(docs),
        "usable_lines": len(lines),
        "train_lines": len(train),
        "val_lines": len(val),
    }


@step
def train_cpt_step(
    base_model: Optional[str] = None,
    output_dir: Optional[str] = None,
    corpus_dir: Optional[str] = None,
) -> TrainSummary:
    """Run CPT fine-tuning using the prepared corpus."""
    load_dotenv()

    if base_model is not None:
        os.environ["BASE_MODEL"] = base_model
    if output_dir is not None:
        os.environ["OUTPUT_DIR"] = output_dir
    if corpus_dir is not None:
        os.environ["CORPUS_DIR"] = corpus_dir

    cfg = train_cpt_module.CPTConfig()
    Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)

    # Run the training loop defined in train_cpt.main()
    train_cpt_module.main()

    metrics_path = Path(cfg.output_dir) / "metrics.json"
    metrics: Dict[str, Any] = {}
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text())
        except json.JSONDecodeError:
            metrics = {}

    return {
        "base_model": cfg.model_id,
        "output_dir": cfg.output_dir,
        "corpus_dir": cfg.corpus_dir,
        "metrics_path": str(metrics_path),
        "metrics": metrics,
    }

