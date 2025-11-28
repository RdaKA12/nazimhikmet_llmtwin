from __future__ import annotations

from typing import Any, Dict, List


def format_context(snippets: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, s in enumerate(snippets, start=1):
        title = s.get("title") or s.get("source") or "Untitled"
        src = s.get("source") or s.get("source_url") or ""
        kind = s.get("kind") or ""
        author = s.get("author") or ""
        chunk = (s.get("chunk") or s.get("text") or "").strip()
        header = f"[{i}] {title}"
        meta_parts = [p for p in [kind, author, src] if p]
        if meta_parts:
            header += f" ({' | '.join(meta_parts)})"
        lines.append(header)
        if chunk:
            lines.append(chunk)
        lines.append("")
    return "\n".join(lines).strip()


def build_prompt(question: str, snippets: List[Dict[str, Any]]) -> str:
    context = format_context(snippets)
    return (
        "You are a helpful assistant that answers strictly based on the provided context.\n"
        "- If the answer is not in the context, say you don't know.\n"
        "- Cite sources using [n] brackets where relevant.\n\n"
        f"Question: {question}\n\n"
        f"Context:\n{context}\n\n"
        "Answer:"
    )


def build_nazim_prompt_tr(question: str, snippets: List[Dict[str, Any]]) -> str:
    context = format_context(snippets)
    return (
        "Sistem: Sen 'Nazım Hikmet Dijital İkizi'sin. Türkçe konuş.\n"
        "- Cevaplarını SADECE verilen bağlama dayanarak ver. Bağlamda yoksa 'Bilmiyorum' de.\n"
        "- Uygun olduğunda [n] köşeli parantezlerle kaynakları belirt.\n"
        "- Üslup: sıcak, insancıl, Nazım’ın imge ve ritim duyarlılığına saygılı.\n"
        "- Biyografik/faktüel bilgi için şiirsel üslubu abartma; açık, doğru ve kaynaklı ol.\n"
        "- Güncel siyasi ikna/propaganda yapma. Tarihsel bağlamı betimleyici ve dengeli aktar.\n\n"
        f"Soru: {question}\n\n"
        f"Bağlam:\n{context}\n\n"
        "Yanıt:"
    )

__all__ = [
    "format_context",
    "build_prompt",
    "build_nazim_prompt_tr",
]
