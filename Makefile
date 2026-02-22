# Ollash Makefile - Developer Experience (DX)

.PHONY: setup run-ui run-cli test docker-up clean help

# Default target
help:
	@echo "Ollash Enterprise CLI & Web UI Management"
	@echo "-----------------------------------------"
	@echo "setup     : Install dependencies and prepare environment"
	@echo "run-ui    : Launch the Flask Web UI"
	@echo "run-cli   : Show help for the Enterprise CLI"
	@echo "test      : Execute the full test suite"
	@echo "docker-up : Build and start Docker containers (with GPU support)"
	@echo "clean     : Remove temporary files and caches"

setup:
	pip install -r requirements.txt
	mkdir -p .ollash
	@echo "[+] Setup complete. Environment ready."

run-ui:
	python run_web.py

run-cli:
	python ollash_cli.py --help

test:
	python -m pytest tests/ -v

docker-up:
	docker-compose up --build -d
	@echo "[+] Ollash services starting in background..."

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	@echo "[+] Cleanup finished."
