# Makefile for PR Validation System

.PHONY: help setup install clean test lint format run docker-build docker-run deploy docs

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PIP := pip
VENV := venv
DOCKER_IMAGE := pr-validation-system
DOCKER_TAG := latest

# Help target
help: ## Show this help message
	@echo "PR Validation System - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup development environment
setup: ## Set up development environment
	@echo "Setting up development environment..."
	@./scripts/setup.sh

# Install dependencies
install: ## Install Python dependencies
	@echo "Installing dependencies..."
	@$(PYTHON) -m pip install --upgrade pip
	@$(PIP) install -r requirements.txt

# Create virtual environment
venv: ## Create virtual environment
	@echo "Creating virtual environment..."
	@$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created. Activate with: source $(VENV)/bin/activate"

# Clean up
clean: ## Clean up generated files and caches
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name ".coverage" -delete
	@rm -rf .pytest_cache
	@rm -rf .mypy_cache
	@rm -rf htmlcov
	@rm -rf dist
	@rm -rf build
	@rm -rf *.egg-info
	@echo "Cleanup completed"

# Run tests
test: ## Run all tests
	@echo "Running tests..."
	@$(PYTHON) -m pytest tests/ -v

# Run unit tests only
test-unit: ## Run unit tests
	@echo "Running unit tests..."
	@$(PYTHON) -m pytest tests/unit/ -v

# Run integration tests only
test-integration: ## Run integration tests
	@echo "Running integration tests..."
	@$(PYTHON) -m pytest tests/integration/ -v

# Run tests with coverage
test-coverage: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	@$(PYTHON) -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# Lint code
lint: ## Run linting checks
	@echo "Running linting checks..."
	@$(PYTHON) -m flake8 src/ api/ tests/
	@$(PYTHON) -m mypy src/ api/ --ignore-missing-imports

# Format code
format: ## Format code with black and isort
	@echo "Formatting code..."
	@$(PYTHON) -m black src/ api/ tests/
	@$(PYTHON) -m isort src/ api/ tests/

# Check code formatting
format-check: ## Check code formatting without changes
	@echo "Checking code formatting..."
	@$(PYTHON) -m black --check src/ api/ tests/
	@$(PYTHON) -m isort --check-only src/ api/ tests/

# Run development server
run: ## Run the development server
	@echo "Starting development server..."
	@uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run with specific environment
run-prod: ## Run with production settings
	@echo "Starting production server..."
	@ENVIRONMENT=production uvicorn api.main:app --host 0.0.0.0 --port 8000

# Docker commands
docker-build: ## Build Docker image
	@echo "Building Docker image..."
	@docker build -f docker/Dockerfile -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run: ## Run Docker container
	@echo "Running Docker container..."
	@docker run -d -p 8000:8000 --env-file .env $(DOCKER_IMAGE):$(DOCKER_TAG)

docker-compose-up: ## Start services with docker-compose
	@echo "Starting services with docker-compose..."
	@cd docker && docker-compose up -d

docker-compose-down: ## Stop services with docker-compose
	@echo "Stopping services..."
	@cd docker && docker-compose down

docker-compose-logs: ## Show docker-compose logs
	@cd docker && docker-compose logs -f

# Database commands
db-upgrade: ## Run database migrations
	@echo "Running database migrations..."
	@alembic upgrade head

db-downgrade: ## Downgrade database by one revision
	@echo "Downgrading database..."
	@alembic downgrade -1

db-migration: ## Create a new database migration
	@echo "Creating new migration..."
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Documentation
docs: ## Build documentation
	@echo "Building documentation..."
	@mkdocs build

docs-serve: ## Serve documentation locally
	@echo "Serving documentation..."
	@mkdocs serve

# Deployment
deploy: ## Deploy to production
	@echo "Deploying to production..."
	@./scripts/deploy.sh

deploy-docker: ## Deploy using Docker
	@./scripts/deploy.sh docker production

deploy-k8s: ## Deploy to Kubernetes
	@./scripts/deploy.sh kubernetes production

deploy-azure: ## Deploy to Azure
	@./scripts/deploy.sh azure production

# Security checks
security: ## Run security checks
	@echo "Running security checks..."
	@$(PYTHON) -m pip install safety
	@safety check
	@$(PYTHON) -m pip install bandit
	@bandit -r src/ api/

# Pre-commit hooks
pre-commit: ## Run pre-commit hooks
	@echo "Running pre-commit hooks..."
	@pre-commit run --all-files

pre-commit-install: ## Install pre-commit hooks
	@echo "Installing pre-commit hooks..."
	@pre-commit install

# Environment setup
env: ## Create .env file from example
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env file created from .env.example"; \
		echo "Please update it with your configuration"; \
	else \
		echo ".env file already exists"; \
	fi

# Show current environment
show-env: ## Show current environment variables
	@echo "Current environment variables:"
	@cat .env | grep -v '^#' | grep -v '^$$'

# Health check
health-check: ## Check if API is healthy
	@echo "Checking API health..."
	@curl -f http://localhost:8000/api/health || echo "API is not running"

# Version info
version: ## Show version information
	@echo "PR Validation System"
	@echo "Version: $(shell grep 'version =' pyproject.toml | cut -d'"' -f2)"
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Docker: $(shell docker --version 2>/dev/null || echo 'Not installed')"
	@echo "kubectl: $(shell kubectl version --client --short 2>/dev/null || echo 'Not installed')"

# Development shortcuts
dev: venv install ## Quick development setup
	@echo "Development environment ready!"
	@echo "Activate virtual environment with: source $(VENV)/bin/activate"

# CI/CD shortcuts
ci: format-check lint test ## Run CI checks

# Full check before commit
check: format lint test security ## Run all checks before commit

# Monitor logs
logs: ## Tail application logs
	@tail -f logs/*.log 2>/dev/null || echo "No log files found"

# Database shell
db-shell: ## Open database shell
	@docker-compose -f docker/docker-compose.yml exec db psql -U postgres -d pr_validation

# Redis CLI
redis-cli: ## Open Redis CLI
	@docker-compose -f docker/docker-compose.yml exec redis redis-cli