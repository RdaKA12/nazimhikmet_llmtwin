from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


def create_app() -> FastAPI:
    load_dotenv()

    app = FastAPI(title="Nazim Twin Web UI")

    static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "static")
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")

    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(templates_dir, exist_ok=True)

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=templates_dir)

    api_base = os.getenv("NAZIM_API_URL", "http://localhost:8000")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Any:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "api_base": api_base,
            },
        )

    @app.post("/ask")
    async def proxy_ask(payload: Dict[str, Any]) -> JSONResponse:
        question = (payload.get("question") or "").strip()
        k = payload.get("k") or 5
        max_tokens = payload.get("max_tokens") or 512
        language = (payload.get("language") or "tr").strip().lower()

        try:
            resp = requests.post(
                f"{api_base.rstrip('/')}/ask",
                json={
                    "question": question,
                    "k": k,
                    "max_tokens": max_tokens,
                    "language": language,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return JSONResponse(data)
        except requests.RequestException as exc:
            return JSONResponse(
                {"detail": f"Upstream API error: {exc}"},
                status_code=502,
            )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8090")))
