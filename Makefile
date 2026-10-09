.PHONY: seed test eval run frontend-build frontend-test demo-reset

demo-reset:
	python backend/data/generate_seed.py
	python backend/app/services/ingestion/seed_loader.py

seed:
	python backend/app/services/ingestion/seed_loader.py

test:
	python -m pytest backend/tests -v

eval:
	PYTHONPATH=backend python -m app.eval.run_eval --adversarial

run:
	PYTHONPATH=backend uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

frontend-build:
	cd frontend && npm run build

frontend-test:
	node frontend/test-e2e.mjs
	node frontend/test-step12.mjs
	node frontend/test-step13.mjs
	node frontend/test-step14.mjs
	node frontend/test-step15.mjs
	node frontend/test-step16.mjs
	node frontend/test-step17.mjs
	node frontend/test-step18.mjs


