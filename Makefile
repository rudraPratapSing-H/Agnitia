.PHONY: help setup dev test reset demo run-backend run-frontend

help:
	@echo "Agnitia Dev Commands:"
	@echo "  make setup   - Install backend and frontend dependencies"
	@echo "  make dev     - Run backend (:8000) and frontend (:5173) concurrently"
	@echo "  make test    - Run backend unit tests with pytest"
	@echo "  make reset   - Trigger /api/reset to restore all services to healthy"
	@echo "  make demo    - Start in cached demo mode (guaranteed offline stability)"

setup:
	python -m pip install -r backend/requirements.txt
	cd frontend && npm install

run-backend:
	python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

run-frontend:
	cd frontend && npm run dev

dev:
	@echo "Starting backend and frontend..."
	python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload & cd frontend && npm run dev

test:
	python -m pytest backend/tests -v

reset:
	curl -s -X POST http://localhost:8000/api/reset

demo:
	DEMO_MODE=cache python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
