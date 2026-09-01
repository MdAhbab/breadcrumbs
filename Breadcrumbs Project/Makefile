# Breadcrumbs — one command per thing you might want to do.
#
# Works on macOS, Linux and WSL2. Everything except `fabric-*` runs without
# Docker. Requires Python 3.10-3.12 (3.13+ has no PyTorch wheels yet) and Node 18+.

PY ?= python3.11
VENV := .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
BIN := $(VENV)/Scripts
endif

.DEFAULT_GOAL := help
.PHONY: help setup test test-fast lint demo api web build clean fabric-up fabric-deploy fabric-down verify bench bench-quick attacks

help:
	@echo "Breadcrumbs"
	@echo "  make setup         create the venv and install everything"
	@echo "  make test          run all tests (ledger, gate, merkle, learning, API)"
	@echo "  make test-fast     skip the tests that train models"
	@echo "  make lint          ruff"
	@echo "  make demo          the twelve-act end-to-end demo"
	@echo "  make attacks       run only the tests that attack the system"
	@echo "  make bench         measure everything; writes ../results/*.json and results.tex"
	@echo "  make bench-quick   the same, smaller, for a sanity check"
	@echo "  make verify        prove the ledger's integrity from scratch"
	@echo "  make api           start the API on :8000"
	@echo "  make web           start the frontend on :5173"
	@echo "  make fabric-up     real Hyperledger Fabric (needs Docker + ~16GB)"
	@echo "  make clean         delete venv, databases, build output"

$(VENV):
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

setup: $(VENV)
	$(BIN)/pip install -e ".[ml,api,dev]"
	@command -v npm >/dev/null && cd frontend && npm install || echo "npm not found; skipping frontend"
	@echo
	@echo "Ready. Try:  make demo"

test:
	$(BIN)/python -m pytest

test-fast:
	$(BIN)/python -m pytest -m "not slow"

lint:
	$(BIN)/ruff check model backend

demo:
	$(BIN)/python -m model.demo

attacks:
	$(BIN)/python -m pytest -k "attack or forge or collud or withhold or trapdoor or fork" -v

# Every number in the report comes from here. to_latex writes results.tex beside
# main.tex; anything not measured renders as a bold ?? in the PDF rather than
# quietly appearing as something plausible.
bench:
	$(BIN)/python -m model.bench.bench_identity
	$(BIN)/python -m model.bench.bench_ledger --documents 200
	$(BIN)/python -m model.bench.bench_accumulator --bits 3072
	$(BIN)/python -m model.bench.to_latex

bench-quick:
	$(BIN)/python -m model.bench.bench_identity
	$(BIN)/python -m model.bench.bench_ledger --documents 60
	$(BIN)/python -m model.bench.bench_accumulator --bits 2048 --quick
	$(BIN)/python -m model.bench.to_latex

verify:
	@$(BIN)/python -c "from model.consortium import build; \
	c = build(); \
	print('\n'.join(f'{n}: {ch.height} blocks, integrity {ch.verify_chain()}' \
	for n, ch in c.network.channels.items()))"

api:
	cd backend && ../$(BIN)/uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

fabric-up:
	cd model/fabric/network && ./deploy.sh up

fabric-deploy:
	cd model/fabric/network && ./deploy.sh deploy

fabric-down:
	cd model/fabric/network && ./deploy.sh down

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist
	rm -f backend/*.db *.db
	rm -rf model/datagen/corpus .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
