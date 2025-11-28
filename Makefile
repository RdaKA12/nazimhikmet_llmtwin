.PHONY: up down logs status rebuild ps

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f zenml_server pipeline

status:
	docker compose exec pipeline bash -lc "zenml status || true"

rebuild:
	docker compose build --no-cache && docker compose up -d

ps:
	docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

.PHONY: embed verify prepare-corpus finetune-cpt

embed:
	python -m src.etl.ingest_embeddings

verify:
	python -m src.etl.verify_embeddings "Nazim'in umuda dair sozleri"

prepare-corpus:
	python -m src.fine_tune.prepare_corpus

finetune-cpt:
	python -m src.fine_tune.train_cpt
