# Nazim Hikmet Digital Twin

This project builds a small “digital twin” for Nazim Hikmet: it crawls poem / news / biography content, normalizes and stores it in MongoDB + Qdrant, and serves RAG-style answers via Ollama (or any OpenAI-compatible endpoint). Docker Compose brings up Mongo, Qdrant, the ZenML pipeline and the API in one go; you can also use a simple web chat UI on top.

> **Copyright notice:** Nazim Hikmet’s works are under copyright until 2033. This repo does **not** contain full copyrighted texts, corpus JSON dumps, embedding collections or trained model weights; these are excluded via `.gitignore`. Keep your data local and ensure compliance with your local law before exposing anything publicly.

## Architecture (overview)
- **Crawler / ETL (ZenML pipeline):** Reads sources from `configs/sources.yaml` and runs crawl → normalize → dedup → store (Mongo) → embed (Qdrant). The `pipeline` container is triggered automatically by `docker compose`.
- **Data layer:** MongoDB stores raw / deduplicated documents; Qdrant stores vector embeddings.
- **LLM / RAG API:** FastAPI app in `src/api/app.py` exposes `/health` and `/ask`. Default provider is Ollama. The Nazim persona is configured in `Modelfile.nazim`.
- **Web UI:** Small FastAPI + Jinja single-page chat UI (default port `8090`).
- **Fine-tune (CPT):** `src/zen/pipelines/finetune_pipeline.py` prepares a text corpus and runs continued pretraining with Hugging Face Transformers (GPU recommended).

## Quick start (Docker)
1) **Requirements:** Docker, Docker Compose, and Ollama (for the LLM).

2) **Prepare environment file:**
   ```bash
   cp .env.example .env
   ```
   Key variables:
   - `MONGO_URL`, `QDRANT_URL`, `QDRANT_COLLECTION`
   - `LLM_PROVIDER=ollama` (default)
   - `LLM_MODEL_ID=nazim-nazim3.1` (recommended) or any other local Ollama model
   - `OLLAMA_API_URL=http://localhost:11434`
   - Web UI: `WEB_PORT=8090` (default)

3) **Create the Nazim persona model in Ollama (recommended):**
   ```bash
   ollama create nazim-nazim3.1 -f Modelfile.nazim
   ```
   Then set `LLM_MODEL_ID=nazim-nazim3.1` in `.env`.

4) **Start services:**
   ```bash
   docker compose up -d --build
   ```
   You should now have:
   - ZenML server: `http://localhost:8237`
   - API: `http://localhost:8000`
   - Qdrant: `http://localhost:6333`
   - Web UI: `http://localhost:8090`

   The `pipeline` container runs `src.ui.zen_run` and executes the crawl → embed pipeline. To follow logs:
   ```bash
   docker compose logs -f pipeline
   ```

5) **API smoke test:**
   ```bash
   curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{ "question": "Can you explain Nazim Hikmet'\''s view on hope?", "k": 5, "language": "tr" }'
   ```

6) **Web chat:**
   - With the `web` service defined in `docker-compose.yml`, just open:
     - `http://localhost:8090`
   - The UI talks to the backend API via `NAZIM_API_URL`:
     - Inside Docker: `http://api:8000`
     - On host (if you run the UI directly): defaults to `http://localhost:8000`
   - Optional: run the UI directly for development:
     ```bash
     uvicorn src.ui.web:app --host 0.0.0.0 --port ${WEB_PORT:-8090}
     ```

## LLM options
- **Ollama (default):**
  - `LLM_PROVIDER=ollama`
  - `LLM_MODEL_ID=<ollama-model-name>`
  - `OLLAMA_API_URL=http://localhost:11434`
  Recommended: use the persona model `nazim-nazim3.1` created from `Modelfile.nazim`.

- **OpenAI-compatible backends (optional):**
  - `LLM_PROVIDER=openai_compat`
  - `OPENAI_COMPAT_URL=http://your-host:your-port/v1`
  - `LLM_MODEL_ID=<model_id_exposed_by_server>`
  - `OPENAI_API_KEY=<token_if_required>`

## Source configuration
- All sources are defined in `configs/sources.yaml`.
- `SAFE_MODE` (from env or file) can be used to shorten texts to safer summaries.
- To add a new site, add a new source block with the appropriate `kind` and CSS selectors.

## Fine-tune (CPT) pipeline
- Requires a GPU for practical training.
- Run inside the `pipeline` container:
  ```bash
  docker compose exec pipeline bash -lc "python -m src.ui.zen_finetune"
  ```
  Controlled via env variables:
  - `BASE_MODEL`
  - `OUTPUT_DIR`
  - `CORPUS_DIR`
  - `INPUT_JSON` (default `digital_twin.documents.json`, which is **not** committed)

- To run manually on the host:
  ```bash
  python -m src.fine_tune.prepare_corpus
  pip install -r requirements-train.txt
  python -m src.fine_tune.train_cpt
  ```

## Useful commands
- Bring everything up:
  ```bash
  docker compose up -d --build
  ```
- Follow logs:
  ```bash
  docker compose logs -f pipeline
  docker compose logs -f api
  ```
- Run tests:
  ```bash
  pytest
  ```

## Directory overview
- `configs/` – source configuration (`sources.yaml`)
- `docker/` – Dockerfiles for the pipeline image
- `src/api/` – FastAPI app (`/health`, `/ask`)
- `src/ui/web.py` – web chat UI (default port 8090)
- `src/zen/` – ZenML pipelines (crawl, finetune) and steps
- `src/etl/` – embedding, chunking, store/dedup/normalize
- `src/crawler/` – crawlers per site/content type
- `src/fine_tune/` – corpus preparation + CPT training scripts
- `static/`, `templates/` – web UI static assets

## License and copyright
- The code in this repository is licensed under the MIT License (see `LICENSE`).
- All crawled or generated textual content based on external sources remains the copyright of the original authors and publishers. Do not redistribute copyrighted material unless you have the right to do so.

