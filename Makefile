PY ?= python3
VENV ?= .venv
PIP = $(VENV)/bin/pip
PYTHON = $(VENV)/bin/python

.PHONY: venv install dev lint test run ui-install ui-dev backtest clean

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

lint:
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/ruff format --check src tests

fmt:
	$(VENV)/bin/ruff format src tests
	$(VENV)/bin/ruff check --fix src tests

test:
	$(VENV)/bin/pytest

run:
	$(VENV)/bin/uvicorn billionaire.app:app --host $${API_HOST:-0.0.0.0} --port $${API_PORT:-8000} --reload

backtest:
	$(PYTHON) scripts/run_sample_backtest.py

ui-install:
	cd ui/dashboard && npm install

ui-dev:
	cd ui/dashboard && npm run dev

ui-build:
	cd ui/dashboard && npm run build

clean:
	rm -rf $(VENV) build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache
