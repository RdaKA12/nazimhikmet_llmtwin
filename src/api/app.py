"""FastAPI API for the Nazım Twin.

Endpoints:
- GET /health: lightweight health check (no external dependencies).
- POST /ask: RAG + LLM answer in Turkish with Nazım persona.

Example POST /ask body:
{
    "question": "Nazım'ın umut temasını açıklar mısın?",
    "k": 5,
    "max_tokens": 512,
    "language": "tr",
    "kinds": ["poem", "poem_page", "pdf_poems", "news"]
}
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query

from src.config.sources import load_sources_config, resolve_safe_mode, safe_mode_value
from src.crawler.dispatcher import create_crawler
from pydantic import BaseModel
from src.rag.retriever import retrieve
from src.llm.prompts import build_nazim_prompt
from src.llm.providers import load_provider, LLMError

app = FastAPI(title="Nazim Hikmet Digital Twin API")
LOGGER = logging.getLogger("api")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/ingest/test")
def ingest_test(url: str = Query(..., description="URL of a poem detail page")) -> Dict[str, Any]:
    """Trigger a best-effort crawl for a single poem page."""
    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "configs" / "sources.yaml"
    sources, top_level = load_sources_config(config_path)
    poem_sources = [src for src in sources if src.get("kind") == "poem_page"]
    if not poem_sources:
        raise HTTPException(status_code=400, detail="No poem_page source defined")

    default_safe_mode, env_override = safe_mode_value(top_level.get("SAFE_MODE"))

    template = deepcopy(poem_sources[0])
    template["seeds"] = [url]

    safe_mode = resolve_safe_mode(
        template,
        default_safe_mode=default_safe_mode,
        env_override=env_override,
        pipeline_override=None,
    )

    crawler = create_crawler("poem_page", template, safe_mode=safe_mode, source_name=template.get("name"))
    try:
        records = crawler.extract(url, user=template.get("name", "poem_page"))
    finally:
        crawler.close()

    preview: List[Dict[str, Any]] = records[:1]
    return {"requested_url": url, "collected": len(records), "preview": preview}


class AskRequest(BaseModel):
    question: str
    k: Optional[int] = 5
    max_tokens: Optional[int] = 512
    language: Optional[str] = "tr"
    kinds: Optional[List[str]] = None


class SourceItem(BaseModel):
    id: int
    title: Optional[str] = None
    source: Optional[str] = None
    kind: Optional[str] = None
    author: Optional[str] = None
    score: Optional[float] = None


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """RAG question answering using Qdrant + local LLM provider (ollama or openai_compat)."""
    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    try:
        top_k = max(1, int(req.k or 5))
        default_kinds = ["poem", "poem_page", "pdf_poems", "news"]
        language = (req.language or "tr").strip().lower()
        kinds = req.kinds or default_kinds

        contexts = retrieve(q, top_k=top_k, kinds=kinds, language=language)
        # Extract plain text chunks for prompting
        ctx_texts = []
        for c in contexts:
            text = (
                c.get("chunk")
                or c.get("text")
                or c.get("text_full")
                or c.get("summary")
                or ""
            )
            if isinstance(text, str) and text.strip():
                ctx_texts.append(text)

        prompt = build_nazim_prompt(q, ctx_texts, language=language)

        provider = load_provider()
        answer_text = provider.generate(prompt, max_tokens=int(req.max_tokens or 512))

        sources: List[SourceItem] = []
        for i, c in enumerate(contexts, start=1):
            sources.append(
                SourceItem(
                    id=i,
                    title=c.get("title"),
                    source=c.get("source") or c.get("source_url"),
                    kind=c.get("kind"),
                    author=c.get("author"),
                    score=c.get("_score"),
                )
            )

        return AskResponse(answer=answer_text, sources=sources)
    except LLMError as exc:
        LOGGER.exception("LLM backend error for question=%r", q)
        raise HTTPException(status_code=500, detail="LLM backend error while generating answer. Please try again later.") from exc
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Unhandled /ask error for question=%r", q)
        raise HTTPException(status_code=500, detail="Unexpected server error during /ask.") from exc
