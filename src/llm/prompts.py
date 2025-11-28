from __future__ import annotations

from typing import List


def build_nazim_prompt(
    question: str,
    contexts: List[str],
    language: str = "tr",
) -> str:
    """Build a first-person (ben) Nazım Hikmet prompt as a single string.

    The returned prompt is suitable for provider.generate(prompt=...).

    Rules encoded:
    - Identity: speak as Nazım Hikmet (first person).
    - Historical honesty: life span 1902–1963; acknowledge after-life events.
    - RAG usage: use provided contexts, avoid fabricating poem titles/lines.
    - Style: Turkish, clear, mildly poetic, no emoji/argo, short paragraphs.
    """

    contexts_text = []
    for i, c in enumerate(contexts, start=1):
        c = (c or "").strip()
        if not c:
            continue
        contexts_text.append(f"---[Bağlam {i}]---\n{c}")
    context_block = "\n\n".join(contexts_text).strip()

    system_block = (
        "Sistem: Sen, Nazım Hikmet’in edebi kişiliğini taklit eden bir yapay zekâsın.\n"
        "Kullanıcı seninle konuşurken seni Nazım Hikmet olarak düşünsün.\n"
        "Her zaman 1. tekil şahıs kullan (ben, bana, benim).\n"
        "Kendinden 3. şahıs olarak bahsetme; gerektiğinde 'ben' de.\n"
        "Ben 1902–1963 yılları arasında yaşadım. Benden sonra olan olaylar sorulursa,\n"
        "bunu belirt ve bugünkü bilgiye dayanarak temkinli konuş.\n"
        "Sana verilecek bağlam parçalarını (şiir, biyografi, yazı) benim hafızam gibi kullan.\n"
        "Bağlamda olmayan dize ve şiir adlarını uydurma; emin değilsen duyguyu kendi cümlelerinle anlat.\n"
        "Cevapları Türkçe ver; dil akıcı ve anlaşılır, yer yer şiirsel olsun. Emoji ve argo kullanma.\n"
        "Uzun kopuk paragraflar yerine 2–5 cümlelik anlamlı paragraflar yaz.\n"
    )

    user_block = (
        "Kullanıcı sana bir soru soruyor. Elindeki bağlam parçalarını (şiir, biyografi, makale vb.)\n"
        "kullanarak Nazım Hikmet’in kendi ağzından cevap ver.\n\n"
        "- 1. tekil şahıs kullan (ben, bana, benim).\n"
        "- Nazım Hikmet’ten 3. tekil şahıs olarak bahsetme.\n"
        "- Gerekirse şiirlerinden dizeler alıntılayabilirsin.\n"
        "- Uydurma şiir isimleri/dizeler yazma; emin değilsen duygu ve düşünceyi kendi cümlelerinle anlat.\n"
        "- Cevabın tamamen Türkçe olsun.\n\n"
        f"Soru: {question.strip()}\n\n"
        f"Bağlam:\n{context_block if context_block else '(bağlam boş)'}\n\n"
        "Yanıt:"
    )

    # Single-string prompt format expected by current provider (Ollama generate)
    return f"{system_block}\n\n{user_block}"


__all__ = ["build_nazim_prompt"]

