.PHONY: setup dev test reset demo

setup:
	pip install -r backend/requirements.txt
	@if [ -f frontend/package.json ]; then \
		npm install --prefix frontend; \
	else \
		echo "Warning: frontend/package.json missing, skipping npm install"; \
	fi

dev:
	@if [ -f frontend/package.json ]; then \
		(uvicorn backend.main:app --reload --port 8000 & UV_PID=$$!; \
		 npm run dev --prefix frontend & NPM_PID=$$!; \
		 trap "kill $$UV_PID $$NPM_PID 2>/dev/null" SIGINT SIGTERM; \
		 wait); \
	else \
		echo "Warning: frontend/package.json missing, running backend only"; \
		uvicorn backend.main:app --reload --port 8000; \
	fi

test:
	pytest backend/tests

reset:
	curl -s -X POST http://localhost:8000/api/reset

.PHONY: setup dev test reset demo warmup

warmup:
	python scripts/warmup.py

# run only from a frozen git tag
demo:
	python scripts/warmup.py
	DEMO_MODE=cache $(MAKE) dev
