from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


class LLMProvider:
    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        raise NotImplementedError


class LLMError(RuntimeError):
    pass


class OllamaLLM(LLMProvider):
    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None) -> None:
        # Defaults tailored for Docker on Windows: host.docker.internal resolves to host
        self.base_url = base_url or os.getenv("OLLAMA_API_URL", "http://host.docker.internal:11434")
        self.model = model or os.getenv("OLLAMA_MODEL") or os.getenv("LLM_MODEL_ID") or "llama3.2:3b"

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max(1, int(max_tokens or 512)),
                "temperature": 0.2,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return (data.get("response") or "").strip()
        except requests.RequestException as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc
        except ValueError as exc:
            raise LLMError("Ollama JSON decode failed") from exc


class OpenAICompatLLM(LLMProvider):
    """Calls an OpenAI-compatible /chat/completions endpoint (e.g., vLLM)."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL_ID") or "gpt-3.5-turbo"
        self.base_url = base_url or os.getenv("OPENAI_COMPAT_URL", "http://localhost:8000/v1")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def generate(self, prompt: str, *, max_tokens: int = 512) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You answer strictly from the provided context."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        except requests.RequestException as exc:
            raise LLMError(f"OpenAI‑compat request failed: {exc}") from exc
        except ValueError as exc:
            raise LLMError("OpenAI‑compat JSON decode failed") from exc


def load_provider() -> LLMProvider:
    provider = (os.getenv("LLM_PROVIDER") or "ollama").lower()
    if provider == "openai_compat":
        return OpenAICompatLLM()
    # default to ollama for local-first
    return OllamaLLM()
