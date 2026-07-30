# ============================================================
# 电气图纸绘制机器人 — Makefile (cross-platform)
# ============================================================
# Usage:
#   make install        Install all dependencies
#   make test           Run full test suite
#   make lint           Lint Python + TypeScript
#   make build          Build frontend for production
#   make dev            Start dev servers (backend + frontend)
#   make docker-build   Build Docker image
#   make docker-run     Run Docker container
# ============================================================

.PHONY: help install install-backend install-frontend test test-backend test-frontend
.PHONY: lint lint-backend lint-frontend format format-backend format-frontend
.PHONY: build build-frontend dev dev-backend dev-frontend clean
.PHONY: docker-build docker-run docker-push release

# Default Python / Node (override with: make PYTHON=python3.13 NODE=node24)
PYTHON  := python3
NODE    := node
NPM     := npm
NPX     := npx

BACKEND_DIR  := backend
FRONTEND_DIR := frontend
TESTS_DIR    := tests

# ── help ────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ── install ─────────────────────────────────────────────────
install: install-backend install-frontend ## Install ALL dependencies

install-backend: ## Install Python dependencies
	$(PYTHON) -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install ruff mypy pytest-cov

install-frontend: ## Install Node.js dependencies
	cd $(FRONTEND_DIR) && $(NPM) ci

# ── test ────────────────────────────────────────────────────
test: test-backend ## Run all tests
	@echo "All tests passed"

test-backend: ## Run Python tests (skip CAD-dependent)
	OPENAI_API_KEY=sk-test \
	MODEL_NAME=gpt-4o-mini \
	DEBUG=true \
	DB_PATH=:memory: \
	CHROMA_PATH=/tmp/chroma-test \
	$(PYTHON) -m pytest $(TESTS_DIR)/ \
		-v --tb=short \
		--cov=$(BACKEND_DIR) \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		-k "not autocad and not cad and not com" \
		-p no:cacheprovider

test-backend-full: ## Run ALL Python tests (requires AutoCAD)
	$(PYTHON) -m pytest $(TESTS_DIR)/ -v --tb=short

test-coverage: test-backend ## Run tests + open HTML coverage report
	@echo "Coverage report: htmlcov/index.html"

# ── lint ─────────────────────────────────────────────────────
lint: lint-backend lint-frontend ## Lint all code

lint-backend: ## Lint Python with ruff
	ruff check $(BACKEND_DIR)/ $(TESTS_DIR)/ --select E,F,W,I,N,UP --ignore E501

lint-frontend: ## TypeScript typecheck
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

# ── format ──────────────────────────────────────────────────
format: format-backend format-frontend ## Format all code

format-backend: ## Format Python with ruff
	ruff check $(BACKEND_DIR)/ $(TESTS_DIR)/ --fix
	ruff format $(BACKEND_DIR)/ $(TESTS_DIR)/

format-frontend: ## Format frontend (if prettier available)
	cd $(FRONTEND_DIR) && $(NPX) prettier --write "src/**/*.{ts,tsx,css}" 2>/dev/null || true

# ── build ───────────────────────────────────────────────────
build: build-frontend ## Build for production

build-frontend: ## Build frontend (Vite)
	cd $(FRONTEND_DIR) && $(NPM) run build

# ── dev ─────────────────────────────────────────────────────
dev: ## Start both dev servers
	@echo "Starting backend (port 8765) and frontend (port 5173)..."
	@echo "Press Ctrl+C to stop both."
	@trap 'kill 0' EXIT; \
		($(PYTHON) $(BACKEND_DIR)/main.py) & \
		(cd $(FRONTEND_DIR) && $(NPM) run dev) & \
		wait

dev-backend: ## Start backend dev server only
	$(PYTHON) $(BACKEND_DIR)/main.py

dev-frontend: ## Start frontend dev server only
	cd $(FRONTEND_DIR) && $(NPM) run dev

# ── docker ──────────────────────────────────────────────────
docker-build: ## Build Docker image
	docker build -t elec-drawing-robot-backend:latest .

docker-run: ## Run Docker container locally
	docker run -p 8765:8765 --env-file .env \
		-v $(PWD)/$(BACKEND_DIR)/data:/app/backend/data \
		elec-drawing-robot-backend:latest

docker-push: ## Build and push to GHCR
	docker build -t ghcr.io/elec-drawing/elec-drawing-robot-backend:latest .
	docker push ghcr.io/elec-drawing/elec-drawing-robot-backend:latest

# ── release ─────────────────────────────────────────────────
release: test lint build ## Pre-release quality gate
	@echo "All quality checks passed — ready to tag and release"
	@echo "Next: git tag v<VERSION> && git push --tags"

# ── clean ───────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/dist-electron
	rm -rf htmlcov .coverage coverage.xml
	rm -rf $(BACKEND_DIR)/data/*.db $(BACKEND_DIR)/data/*.db-wal $(BACKEND_DIR)/data/*.db-shm
	@echo "Cleaned."
