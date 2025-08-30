# AI Agent Dashboard - Development Makefile
# ===========================================

# Variables
SHELL := /bin/bash
PYTHON := python3.11
NODE := node
NPM := npm
DOCKER := docker
DOCKER_COMPOSE := docker-compose

# Project directories
SERVER_DIR := server
CLIENT_DIR := client
MONITORING_DIR := monitoring

# Docker images
BACKEND_IMAGE := ai-agent-dashboard-backend
FRONTEND_IMAGE := ai-agent-dashboard-frontend

# Environment variables
export PYTHONPATH := $(PWD)/$(SERVER_DIR)
export NODE_ENV := development

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
PURPLE := \033[0;35m
CYAN := \033[0;36m
WHITE := \033[0;37m
NC := \033[0m # No Color

# Help target
.PHONY: help
help: ## Show this help message
	@echo -e "${GREEN}AI Agent Dashboard - Development Commands${NC}"
	@echo -e "${BLUE}===============================================${NC}"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "${CYAN}%-25s${NC} %s\n", $$1, $$2}'
	@echo ""

# Development Environment Setup
.PHONY: install
install: install-backend install-frontend install-tools ## Install all dependencies
	@echo -e "${GREEN}✅ All dependencies installed${NC}"

.PHONY: install-backend
install-backend: ## Install Python backend dependencies
	@echo -e "${BLUE}📦 Installing Python dependencies...${NC}"
	cd $(SERVER_DIR) && pip install -r requirements.txt

.PHONY: install-frontend
install-frontend: ## Install Node.js frontend dependencies
	@echo -e "${BLUE}📦 Installing Node.js dependencies...${NC}"
	cd $(CLIENT_DIR) && npm install

.PHONY: install-tools
install-tools: ## Install development tools
	@echo -e "${BLUE}🔧 Installing development tools...${NC}"
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg
	cd $(CLIENT_DIR) && npx playwright install --with-deps

# Development Servers
.PHONY: dev
dev: ## Start all development servers
	@echo -e "${GREEN}🚀 Starting all development servers...${NC}"
	$(MAKE) -j4 dev-backend dev-frontend dev-redis dev-postgres

.PHONY: dev-backend
dev-backend: ## Start backend development server
	@echo -e "${BLUE}🐍 Starting Python backend...${NC}"
	cd $(SERVER_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: dev-frontend
dev-frontend: ## Start frontend development server
	@echo -e "${BLUE}⚛️  Starting React frontend...${NC}"
	cd $(CLIENT_DIR) && npm run dev

.PHONY: dev-full-stack
dev-full-stack: ## Start full development stack with Docker
	@echo -e "${GREEN}🐳 Starting full development stack...${NC}"
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.override.yml up

# Database Operations
.PHONY: dev-postgres
dev-postgres: ## Start PostgreSQL in development mode
	@echo -e "${BLUE}🐘 Starting PostgreSQL...${NC}"
	$(DOCKER) run --name ai-dashboard-postgres -d \
		-e POSTGRES_DB=ai_dashboard \
		-e POSTGRES_USER=aiagent \
		-e POSTGRES_PASSWORD=aiagent123 \
		-p 5432:5432 \
		postgres:14-alpine || $(DOCKER) start ai-dashboard-postgres

.PHONY: dev-redis
dev-redis: ## Start Redis in development mode
	@echo -e "${BLUE}📮 Starting Redis...${NC}"
	$(DOCKER) run --name ai-dashboard-redis -d \
		-p 6379:6379 \
		redis:7-alpine || $(DOCKER) start ai-dashboard-redis

.PHONY: db-migrate
db-migrate: ## Run database migrations
	@echo -e "${BLUE}🗃️  Running database migrations...${NC}"
	cd $(SERVER_DIR) && alembic upgrade head

.PHONY: db-migration
db-migration: ## Create new database migration
	@echo -e "${BLUE}📝 Creating new migration...${NC}"
	@read -p "Migration message: " message; \
	cd $(SERVER_DIR) && alembic revision --autogenerate -m "$$message"

.PHONY: db-reset
db-reset: ## Reset database (WARNING: destructive)
	@echo -e "${RED}⚠️  WARNING: This will delete all data!${NC}"
	@read -p "Are you sure? [y/N]: " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		cd $(SERVER_DIR) && alembic downgrade base && alembic upgrade head; \
		echo -e "${GREEN}✅ Database reset complete${NC}"; \
	else \
		echo -e "${YELLOW}❌ Database reset cancelled${NC}"; \
	fi

# Testing
.PHONY: test
test: test-backend test-frontend ## Run all tests
	@echo -e "${GREEN}✅ All tests completed${NC}"

.PHONY: test-backend
test-backend: ## Run backend tests
	@echo -e "${BLUE}🧪 Running Python tests...${NC}"
	cd $(SERVER_DIR) && python -m pytest tests/ -v --cov=app --cov-report=term-missing

.PHONY: test-frontend
test-frontend: ## Run frontend tests
	@echo -e "${BLUE}🧪 Running frontend tests...${NC}"
	cd $(CLIENT_DIR) && npm run test:coverage

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests
	@echo -e "${BLUE}🎭 Running E2E tests...${NC}"
	cd $(CLIENT_DIR) && npm run test:e2e

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	@echo -e "${BLUE}👀 Running tests in watch mode...${NC}"
	$(MAKE) -j2 test-backend-watch test-frontend-watch

.PHONY: test-backend-watch
test-backend-watch: ## Run backend tests in watch mode
	cd $(SERVER_DIR) && ptw --runner "python -m pytest tests/ -v"

.PHONY: test-frontend-watch
test-frontend-watch: ## Run frontend tests in watch mode
	cd $(CLIENT_DIR) && npm run test

.PHONY: test-integration
test-integration: ## Run integration tests with Docker
	@echo -e "${BLUE}🔗 Running integration tests...${NC}"
	$(DOCKER_COMPOSE) -f docker-compose.test.yml up --build --abort-on-container-exit

# Code Quality
.PHONY: lint
lint: lint-backend lint-frontend ## Run all linters
	@echo -e "${GREEN}✅ All linting completed${NC}"

.PHONY: lint-backend
lint-backend: ## Run backend linting
	@echo -e "${BLUE}🔍 Linting Python code...${NC}"
	cd $(SERVER_DIR) && flake8 app/ && mypy app/ --ignore-missing-imports

.PHONY: lint-frontend
lint-frontend: ## Run frontend linting
	@echo -e "${BLUE}🔍 Linting TypeScript/React code...${NC}"
	cd $(CLIENT_DIR) && npm run lint && npm run type-check

.PHONY: format
format: format-backend format-frontend ## Format all code
	@echo -e "${GREEN}✅ All code formatted${NC}"

.PHONY: format-backend
format-backend: ## Format Python code
	@echo -e "${BLUE}🎨 Formatting Python code...${NC}"
	cd $(SERVER_DIR) && black app/ tests/ && isort app/ tests/

.PHONY: format-frontend
format-frontend: ## Format TypeScript/React code
	@echo -e "${BLUE}🎨 Formatting TypeScript code...${NC}"
	cd $(CLIENT_DIR) && npm run lint:fix

.PHONY: pre-commit
pre-commit: ## Run pre-commit hooks
	@echo -e "${BLUE}🔒 Running pre-commit hooks...${NC}"
	pre-commit run --all-files

# Security
.PHONY: security
security: security-backend security-frontend ## Run security checks
	@echo -e "${GREEN}✅ Security checks completed${NC}"

.PHONY: security-backend
security-backend: ## Run backend security checks
	@echo -e "${BLUE}🔐 Running Python security checks...${NC}"
	cd $(SERVER_DIR) && bandit -r app/ && safety check -r requirements.txt

.PHONY: security-frontend
security-frontend: ## Run frontend security checks
	@echo -e "${BLUE}🔐 Running Node.js security checks...${NC}"
	cd $(CLIENT_DIR) && npm audit --audit-level=high

# Docker Operations
.PHONY: docker-build
docker-build: ## Build Docker images
	@echo -e "${BLUE}🐳 Building Docker images...${NC}"
	$(DOCKER) build -t $(BACKEND_IMAGE):latest ./$(SERVER_DIR)
	$(DOCKER) build -t $(FRONTEND_IMAGE):latest ./$(CLIENT_DIR)

.PHONY: docker-build-prod
docker-build-prod: ## Build production Docker images
	@echo -e "${BLUE}🐳 Building production Docker images...${NC}"
	$(DOCKER) build --target production -t $(BACKEND_IMAGE):latest ./$(SERVER_DIR)
	$(DOCKER) build --target production -t $(FRONTEND_IMAGE):latest ./$(CLIENT_DIR)

.PHONY: docker-test
docker-test: ## Run tests in Docker containers
	@echo -e "${BLUE}🐳 Running Docker tests...${NC}"
	$(DOCKER_COMPOSE) -f docker-compose.test.yml up --build --abort-on-container-exit
	$(DOCKER_COMPOSE) -f docker-compose.test.yml down

.PHONY: docker-up
docker-up: ## Start all services with Docker Compose
	@echo -e "${BLUE}🐳 Starting Docker services...${NC}"
	$(DOCKER_COMPOSE) up -d

.PHONY: docker-down
docker-down: ## Stop all Docker services
	@echo -e "${BLUE}🐳 Stopping Docker services...${NC}"
	$(DOCKER_COMPOSE) down

.PHONY: docker-logs
docker-logs: ## Show Docker logs
	$(DOCKER_COMPOSE) logs -f

.PHONY: docker-clean
docker-clean: ## Clean Docker resources
	@echo -e "${BLUE}🧹 Cleaning Docker resources...${NC}"
	$(DOCKER) system prune -f
	$(DOCKER) volume prune -f

# Production Operations
.PHONY: build
build: build-backend build-frontend ## Build for production
	@echo -e "${GREEN}✅ Production build completed${NC}"

.PHONY: build-backend
build-backend: ## Build backend for production
	@echo -e "${BLUE}📦 Building Python backend...${NC}"
	cd $(SERVER_DIR) && pip install --no-dev

.PHONY: build-frontend
build-frontend: ## Build frontend for production
	@echo -e "${BLUE}📦 Building React frontend...${NC}"
	cd $(CLIENT_DIR) && npm run build

.PHONY: prod-up
prod-up: ## Start production environment
	@echo -e "${BLUE}🚀 Starting production environment...${NC}"
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml up -d

.PHONY: prod-down
prod-down: ## Stop production environment
	@echo -e "${BLUE}🛑 Stopping production environment...${NC}"
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml down

# Monitoring and Logs
.PHONY: logs
logs: ## Show application logs
	@echo -e "${BLUE}📋 Showing application logs...${NC}"
	$(DOCKER_COMPOSE) logs -f backend frontend

.PHONY: logs-backend
logs-backend: ## Show backend logs
	$(DOCKER_COMPOSE) logs -f backend

.PHONY: logs-frontend
logs-frontend: ## Show frontend logs
	$(DOCKER_COMPOSE) logs -f frontend

.PHONY: metrics
metrics: ## Show metrics
	@echo -e "${BLUE}📊 Opening metrics dashboard...${NC}"
	open http://localhost:9090  # Prometheus
	open http://localhost:3000  # Grafana

.PHONY: health
health: ## Check service health
	@echo -e "${BLUE}🏥 Checking service health...${NC}"
	@curl -s http://localhost:8000/healthz | jq . || echo "Backend not available"
	@curl -s http://localhost:5173 | head -5 || echo "Frontend not available"

# Utility Commands
.PHONY: clean
clean: ## Clean temporary files and caches
	@echo -e "${BLUE}🧹 Cleaning temporary files...${NC}"
	find . -type d -name "__pycache__" -exec rm -rf {} + || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete || true
	cd $(CLIENT_DIR) && rm -rf node_modules/.cache dist coverage || true

.PHONY: reset
reset: docker-down clean ## Reset development environment
	@echo -e "${BLUE}🔄 Resetting development environment...${NC}"
	$(DOCKER) container rm ai-dashboard-postgres ai-dashboard-redis || true
	$(MAKE) install
	@echo -e "${GREEN}✅ Environment reset complete${NC}"

.PHONY: backup-db
backup-db: ## Backup database
	@echo -e "${BLUE}💾 Creating database backup...${NC}"
	@timestamp=$$(date +%Y%m%d_%H%M%S); \
	$(DOCKER) exec ai-dashboard-postgres pg_dump -U aiagent ai_dashboard > "backup_$$timestamp.sql" && \
	echo -e "${GREEN}✅ Database backup saved as backup_$$timestamp.sql${NC}"

.PHONY: restore-db
restore-db: ## Restore database from backup
	@echo -e "${BLUE}📥 Restoring database...${NC}"
	@read -p "Backup file path: " backup_file; \
	if [ -f "$$backup_file" ]; then \
		$(DOCKER) exec -i ai-dashboard-postgres psql -U aiagent -d ai_dashboard < "$$backup_file" && \
		echo -e "${GREEN}✅ Database restored from $$backup_file${NC}"; \
	else \
		echo -e "${RED}❌ Backup file not found${NC}"; \
	fi

.PHONY: shell-backend
shell-backend: ## Open Python shell in backend context
	cd $(SERVER_DIR) && python -c "from app.main import app; from app.models import *; print('Backend shell ready')" -i

.PHONY: shell-db
shell-db: ## Open database shell
	$(DOCKER) exec -it ai-dashboard-postgres psql -U aiagent -d ai_dashboard

# Performance Testing
.PHONY: load-test
load-test: ## Run load tests
	@echo -e "${BLUE}⚡ Running load tests...${NC}"
	cd $(CLIENT_DIR) && npx artillery run load-test.yml

.PHONY: benchmark
benchmark: ## Run performance benchmarks
	@echo -e "${BLUE}🏁 Running performance benchmarks...${NC}"
	cd $(SERVER_DIR) && python -m pytest tests/test_performance.py -v

# Documentation
.PHONY: docs
docs: ## Generate documentation
	@echo -e "${BLUE}📚 Generating documentation...${NC}"
	cd $(SERVER_DIR) && python -m pydoc -w app
	cd $(CLIENT_DIR) && npm run docs || echo "Frontend docs not configured"

.PHONY: api-docs
api-docs: ## Open API documentation
	@echo -e "${BLUE}📖 Opening API documentation...${NC}"
	open http://localhost:8000/docs

# Default target
.DEFAULT_GOAL := help