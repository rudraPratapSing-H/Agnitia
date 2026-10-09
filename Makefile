ifeq ($(OS),Windows_NT)
    VENV_PY := $(wildcard .venv/Scripts/python.exe)
    ifneq ($(strip $(VENV_PY)),)
        PYTHON := .venv/Scripts/python.exe
    else
        PYTHON := python
    endif
else
    SHELL := sh
    VENV_PY := $(wildcard .venv/bin/python)
    ifneq ($(strip $(VENV_PY)),)
        PYTHON := .venv/bin/python
    else
        PYTHON := python
    endif
endif

.PHONY: setup dev test reset demo

setup:
	$(PYTHON) -m pip install -r backend/requirements.txt
	@if [ -f frontend/package.json ]; then \
		npm install --prefix frontend || (cd frontend && npm install); \
	else \
		echo "Warning: frontend/package.json missing, skipping npm install"; \
	fi

dev:
	@if [ -f frontend/package.json ]; then \
		($(PYTHON) -m uvicorn backend.main:app --reload --port 8000 & UV_PID=$$!; \
		 npm run dev --prefix frontend & NPM_PID=$$!; \
		 trap "kill $$UV_PID $$NPM_PID 2>/dev/null" SIGINT SIGTERM; \
		 wait); \
	else \
		echo "Warning: frontend/package.json missing, running backend only"; \
		$(PYTHON) -m uvicorn backend.main:app --reload --port 8000; \
	fi

test:
	$(PYTHON) -m pytest backend/tests

reset:
	curl -s -X POST http://localhost:8000/api/reset

# run only from a frozen git tag
demo:
	DEMO_MODE=cache $(MAKE) dev
