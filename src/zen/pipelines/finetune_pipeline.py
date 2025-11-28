from __future__ import annotations

from typing import Any, Dict, Optional

from zenml import pipeline

from src.zen.steps.fine_tune import prepare_corpus_step, train_cpt_step


@pipeline
def finetune_pipeline(
    input_json: Optional[str] = None,
    corpus_dir: str = "data/corpus",
    base_model: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare corpus and run CPT fine-tuning as a ZenML pipeline."""
    corpus_summary = prepare_corpus_step(
        input_json=input_json,
        corpus_dir=corpus_dir,
    )

    train_summary = train_cpt_step(
        base_model=base_model,
        output_dir=output_dir,
        corpus_dir=corpus_dir,
    )

    return {
        "corpus": corpus_summary,
        "train": train_summary,
    }

