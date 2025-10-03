# Makefile
.PHONY: run dev test lint format
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8080
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
test:
	pytest
lint:
	python -m pyflakes app || true
format:
	python -m black .