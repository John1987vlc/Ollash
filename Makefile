# Ollash Makefile - Developer Experience (DX)

.PHONY: setup run-ui run-cli test test-unit test-integration test-e2e \
        lint format security coverage docker-up clean help

# Default target
help:
	@echo "Ollash Enterprise CLI & Web UI Management"
	@echo "-----------------------------------------"
	@echo "setup            : Install all dependencies and prepare environment"
	@echo "run-ui           : Launch the Flask Web UI"
	@echo "run-cli          : Show help for the Enterprise CLI"
	@echo ""
	@echo "--- Testing ---"
	@echo "test             : Execute the full test suite"
	@echo "test-unit        : Run unit tests in parallel (pytest-xdist)"
	@echo "test-integration : Run integration tests"
	@echo "test-e2e         : Run E2E Playwright tests (requires browser)"
	@echo ""
	@echo "--- Quality ---"
	@echo "lint             : Ruff check + format check + flake8"
	@echo "format           : Auto-fix formatting with ruff"
	@echo "security         : Run bandit SAST + safety dependency scan"
	@echo "coverage         : Run unit tests and generate HTML coverage report"
	@echo ""
	@echo "--- Docker ---"
	@echo "docker-up        : Build and start Docker containers (with GPU support)"
	@echo "clean            : Remove temporary files and caches"

setup:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	playwright install chromium
	mkdir -p .ollash
	@echo "[+] Setup complete. Environment ready."

run-ui:
	python run_web.py

run-cli:
	python ollash_cli.py --help

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	python -m pytest tests/ -v

test-unit:
	pytest tests/unit/ -n auto --dist=loadfile -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-e2e:
	pytest tests/e2e/ -m e2e -v --tb=short

# ── Quality ───────────────────────────────────────────────────────────────────

lint:
	ruff check backend/ frontend/ tests/
	ruff format --check backend/ frontend/ tests/
	flake8 backend/ frontend/ tests/ --max-line-length=120 --extend-ignore=E501,W503

format:
	ruff check backend/ frontend/ tests/ --fix
	ruff format backend/ frontend/ tests/

security:
	@echo "[*] Running Bandit SAST scan..."
	bandit -r backend/ -ll
	@echo "[*] Running Safety dependency scan..."
	safety check -r requirements.txt

coverage:
	pytest tests/unit/ --cov=backend --cov-report=html --cov-report=term-missing -v
	@echo "[+] Coverage report generated at htmlcov/index.html"

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker-compose up --build -d
	@echo "[+] Ollash services starting in background..."

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/ .ruff_cache/ htmlcov/ coverage.xml .coverage
	rm -rf test-results/
	@echo "[+] Cleanup finished."
