# Nazim Hikmet Dijital Ikizi

Nazim Hikmet ile ilgili siir/haber/biyografi iceriklerini toplayan, temizleyen, MongoDB + Qdrant'a yukleyen ve Ollama (veya OpenAI-compat) uzerinden RAG cevaplari ureten bir proje. Docker Compose ile Mongo, Qdrant, ZenML pipeline'i ve API tek komutta kalkar; istersen ayrica basit bir web chat arayuzu calistirabilirsin.

> **Telif uyarisi:** Nazim Hikmet eserleri 2033'e kadar telif altinda. SAFE_MODE/ozetleme ayarlari olsa da, kamuya acmadan once yerel hukuka uyumu kontrol et.

## Mimari (kisaca)
- **Crawler/ETL (ZenML pipeline):** `configs/sources.yaml`'dan kaynaklari okuyup crawl -> normalize -> dedup -> store (Mongo) -> embed (Qdrant) calisir. `docker compose` ile pipeline container'i otomatik tetiklenir.
- **Veri katmani:** MongoDB (ham/dedup dokumanlar) + Qdrant (embedding'ler).
- **LLM/RAG:** FastAPI `src/api/app.py` uzerinden `/ask`; varsayilan provider Ollama. Persona icin Modelfile: `Modelfile.nazim`.
- **Web UI:** Kucuk bir FastAPI + Jinja tek sayfa chat (port varsayilan 8090).
- **Fine-tune (CPT):** `src/zen/pipelines/finetune_pipeline.py` GPU ortaminda corpus hazirlayip HF modeli egitir.

## Hizli baslangic (Docker ile)
1) **Gereksinimler:** Docker + Docker Compose, Ollama (LLM icin).  
2) **Env hazirla:**  
   ```bash
   cp .env.example .env
   ```
   Onemli degiskenler:  
   - `MONGO_URL`, `QDRANT_URL`, `QDRANT_COLLECTION`  
   - `LLM_PROVIDER=ollama` (varsayilan)  
   - `LLM_MODEL_ID=nazim-nazim3.1` (tavsiye) veya elindeki baska Ollama modeli  
   - `OLLAMA_API_URL=http://localhost:11434`
   - Web UI icin: `WEB_PORT=8090` (varsayilan)

3) **Nazim personasini Ollama'da olustur (tavsiye):**  
   ```bash
   ollama create nazim-nazim3.1 -f Modelfile.nazim
   ```
   Ardindan `.env`'de `LLM_MODEL_ID=nazim-nazim3.1` kullan.

4) **Servisleri calistir:**  
   ```bash
   docker compose up -d --build
   ```
   - ZenML server: `http://localhost:8237`
   - API: `http://localhost:8000`
   - Qdrant: `http://localhost:6333`
   Pipeline container `src.ui.zen_run` ile crawl->embed akisini tetikler. Log icin:  
   ```bash
   docker compose logs -f pipeline
   ```

5) **API test:**  
   ```bash
   curl -X POST "http://localhost:8000/ask" ^
     -H "Content-Type: application/json" ^
     -d "{ \"question\": \"Nazim'in umut anlayisini anlat\", \"k\": 5, \"language\": \"tr\" }"
   ```

6) **Web chat (istege bagli):** Ayrica host'ta kucuk UI'yi calistir:  
   ```bash
   uvicorn src.ui.web:app --host 0.0.0.0 --port %WEB_PORT%
   ```  
   Sonra tarayici: `http://localhost:8090` (veya belirledigin port). `NAZIM_API_URL` env'i ile arka API adresini degistirebilirsin (varsayilan `http://localhost:8000`).

## LLM secenekleri
- **Ollama (varsayilan):** `LLM_PROVIDER=ollama`, `LLM_MODEL_ID=<ollama-model>`, `OLLAMA_API_URL=http://localhost:11434`. Tavsiye: `nazim-nazim3.1` personasini Modelfile'dan olustur.

## Kaynak konfigurasyonu
- Tum kaynaklar `configs/sources.yaml` icinde.  
- `SAFE_MODE` (env veya dosya) true ise metinler kisa ozetlere indirilir.  
- Yeni site eklemek icin dosyaya yeni blok eklemek yeterli.

## Fine-tune (CPT) pipeline
- GPU gerekir. Docker pipeline container'i icinde calistir:  
  ```bash
  docker compose exec pipeline bash -lc "python -m src.ui.zen_finetune"
  ```
  Env ile ayarla: `BASE_MODEL`, `OUTPUT_DIR`, `CORPUS_DIR`, `INPUT_JSON` (varsayilan `digital_twin.documents.json`).
- Manuel calistirmak istersen:  
  ```bash
  python -m src.fine_tune.prepare_corpus
  pip install -r requirements-train.txt
  python -m src.fine_tune.train_cpt
  ```

## Kullanisli komutlar
- Tum stack: `docker compose up -d --build`
- Log: `docker compose logs -f pipeline` veya `docker compose logs -f api`
- Test: `pytest`

## Dizin ozeti
- `configs/` – kaynak ayarlari (`sources.yaml`)
- `docker/` – Dockerfile'lar (pipeline)
- `src/api/` – FastAPI `/health`, `/ask`
- `src/ui/web.py` – basit web chat UI (port varsayilan 8090)
- `src/zen/` – ZenML pipeline'lari (crawl, finetune) ve adimlari
- `src/etl/` – embedding, chunking, store/dedup/norm
- `src/crawler/` – site-tipine gore crawler'lar
- `src/fine_tune/` – corpus hazirlama + CPT egitim script'leri
- `static/`, `templates/` – web UI statik dosyalari

## Telif ve lisans
- Kodun kendisi icin MIT veya kurum politikasina uygun bir lisans ekleyebilirsin.  
- Cekilen iceriklerin telif haklari orijinal sahiplerine aittir; paylasmadan once kontrol et.
