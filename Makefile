.PHONY: install dev serve train test lint typecheck ui build

install:
	pip install -e ".[dev]"

dev: install
	cd ui/dashboard && npm install

serve:
	python -m ai_trader.cli serve --reload

train:
	python -m ai_trader.cli train

status:
	python -m ai_trader.cli status

test:
	pytest tests/ -q

lint:
	ruff check src/ tests/

lint-fix:
	ruff check --fix src/ tests/

typecheck:
	mypy src/ai_trader/

ui:
	cd ui/dashboard && npm run dev

build-ui:
	cd ui/dashboard && npm run build

build: install build-ui
