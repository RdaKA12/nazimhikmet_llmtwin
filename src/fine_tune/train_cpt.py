from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import datasets as hfds
from datasets import Dataset
from dotenv import load_dotenv
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)


@dataclass
class CPTConfig:
    model_id: str = os.getenv("BASE_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
    output_dir: str = os.getenv("OUTPUT_DIR", "outputs/nazim-cpt")
    corpus_dir: str = os.getenv("CORPUS_DIR", "data/corpus")
    block_size: int = int(os.getenv("BLOCK_SIZE", "1024"))
    lr: float = float(os.getenv("LEARNING_RATE", "2e-4"))
    epochs: int = int(os.getenv("NUM_EPOCHS", "1"))
    batch: int = int(os.getenv("BATCH_SIZE", "2"))
    grad_accum: int = int(os.getenv("GRAD_ACCUM_STEPS", "8"))
    fp16: bool = os.getenv("FP16", "false").lower() == "true"
    bf16: bool = os.getenv("BF16", "true").lower() == "true"
    warmup_ratio: float = float(os.getenv("WARMUP_RATIO", "0.03"))
    weight_decay: float = float(os.getenv("WEIGHT_DECAY", "0.1"))
    save_steps: int = int(os.getenv("SAVE_STEPS", "1000"))
    logging_steps: int = int(os.getenv("LOGGING_STEPS", "25"))


def load_text_dataset(corpus_dir: Path) -> Dict[str, Dataset]:
    train_path = corpus_dir / "train.txt"
    val_path = corpus_dir / "val.txt"
    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError("train.txt / val.txt not found. Run prepare_corpus.py first.")

    train_ds = hfds.load_dataset("text", data_files=str(train_path), split="train")
    val_ds = hfds.load_dataset("text", data_files=str(val_path), split="train")
    return {"train": train_ds, "val": val_ds}


def tokenize_and_group(ds: Dataset, tokenizer, block_size: int) -> Dataset:
    def tokenize(batch):
        return tokenizer(batch["text"])  # type: ignore

    tokenized = ds.map(tokenize, batched=True, remove_columns=["text"])  # type: ignore

    def group_texts(examples):
        concatenated = {k: sum(examples[k], []) for k in examples.keys()}
        total_length = len(concatenated["input_ids"])  # type: ignore
        total_length = (total_length // block_size) * block_size
        result = {
            k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
            for k, t in concatenated.items()
        }
        result["labels"] = result["input_ids"].copy()
        return result

    return tokenized.map(group_texts, batched=True)


def main() -> None:
    load_dotenv()
    cfg = CPTConfig()

    corpus_dir = Path(cfg.corpus_dir)
    ds = load_text_dataset(corpus_dir)

    tokenizer = AutoTokenizer.from_pretrained(cfg.model_id, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    train_tokenized = tokenize_and_group(ds["train"], tokenizer, cfg.block_size)
    val_tokenized = tokenize_and_group(ds["val"], tokenizer, cfg.block_size)

    model = AutoModelForCausalLM.from_pretrained(cfg.model_id)

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    total_train_tokens = len(train_tokenized) * cfg.block_size
    print(
        f"Loaded model: {cfg.model_id}\n"
        f"Train samples: {len(train_tokenized)} | Val samples: {len(val_tokenized)}\n"
        f"Approx. train tokens: {total_train_tokens:,}\n"
    )

    training_args = TrainingArguments(
        output_dir=cfg.output_dir,
        per_device_train_batch_size=cfg.batch,
        per_device_eval_batch_size=cfg.batch,
        gradient_accumulation_steps=cfg.grad_accum,
        learning_rate=cfg.lr,
        num_train_epochs=cfg.epochs,
        weight_decay=cfg.weight_decay,
        warmup_ratio=cfg.warmup_ratio,
        logging_steps=cfg.logging_steps,
        save_steps=cfg.save_steps,
        evaluation_strategy="steps",
        eval_steps=max(50, cfg.logging_steps * 4),
        save_total_limit=2,
        fp16=cfg.fp16,
        bf16=cfg.bf16,
        report_to=["none"],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
        eval_dataset=val_tokenized,
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    trainer.train()
    metrics = trainer.evaluate()
    try:
        ppl = math.exp(metrics.get("eval_loss", float("nan")))
        metrics["perplexity"] = ppl
    except Exception:
        pass

    (Path(cfg.output_dir) / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print("Training complete. Metrics saved:", metrics)


if __name__ == "__main__":
    main()

