.PHONY: help build up down logs clean test lint format terraform-init terraform-plan terraform-apply run-pipeline

# Variables
YEAR ?= 2023
MONTHS ?= 1
STORAGE_TYPE ?= local

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 30
	@echo "Services are up!"
	@echo "Spark UI: http://localhost:8080"
	@echo "Airflow UI: http://localhost:8081 (admin/admin)"
	@echo "PostgreSQL: localhost:5432"

down: ## Stop all services
	docker-compose down

down-clean: ## Stop all services and remove volumes
	docker-compose down -v

logs: ## Show logs from all services
	docker-compose logs -f

logs-spark: ## Show Spark logs
	docker-compose logs -f spark-master spark-worker

logs-airflow: ## Show Airflow logs
	docker-compose logs -f airflow-webserver airflow-scheduler

logs-postgres: ## Show PostgreSQL logs
	docker-compose logs -f postgres

clean: ## Clean up data and logs
	rm -rf data/bronze/* data/silver/* data/gold/* data/raw/*
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

test: ## Run unit tests
	cd spark && pytest tests/ -v --cov=jobs --cov-report=term

test-coverage: ## Run tests with coverage report
	cd spark && pytest tests/ -v --cov=jobs --cov-report=html --cov-report=term
	@echo "Coverage report generated in spark/htmlcov/index.html"

lint: ## Run linting checks
	cd spark && flake8 . --max-line-length=120 --extend-ignore=E203,W503
	cd spark && black --check .
	cd spark && isort --check-only .

format: ## Format code
	cd spark && black .
	cd spark && isort .

terraform-init: ## Initialize Terraform
	cd terraform && terraform init

terraform-plan: ## Plan Terraform changes
	cd terraform && terraform plan

terraform-apply: ## Apply Terraform changes
	cd terraform && terraform apply

terraform-validate: ## Validate Terraform configuration
	cd terraform && terraform fmt -check -recursive
	cd terraform && terraform validate

terraform-format: ## Format Terraform files
	cd terraform && terraform fmt -recursive

# Pipeline execution targets
run-bronze: ## Run bronze ingestion job
	docker-compose exec spark-master spark-submit \
		/opt/spark-app/jobs/bronze_ingestion.py \
		--year $(YEAR) \
		--months $(MONTHS) \
		--storage-type $(STORAGE_TYPE)

run-transform: ## Run dimensional transformation job
	docker-compose exec spark-master spark-submit \
		/opt/spark-app/jobs/dimensional_transform.py \
		--year $(YEAR) \
		--months $(MONTHS) \
		--storage-type $(STORAGE_TYPE)

run-loader: ## Run database loader job
	docker-compose exec spark-master spark-submit \
		--jars /opt/spark/jars/postgresql-42.7.8.jar \
		/opt/spark-app/jobs/db_loader.py \
		--year $(YEAR) \
		--months $(MONTHS) \
		--storage-type $(STORAGE_TYPE)

run-pipeline: ## Run complete pipeline (bronze -> transform -> load)
	@echo "Running complete pipeline for year=$(YEAR), months=$(MONTHS)"
	@make run-bronze YEAR=$(YEAR) MONTHS=$(MONTHS)
	@echo "Bronze ingestion completed"
	@make run-transform YEAR=$(YEAR) MONTHS=$(MONTHS)
	@echo "Dimensional transformation completed"
	@make run-loader YEAR=$(YEAR) MONTHS=$(MONTHS)
	@echo "Database loading completed"
	@echo "Pipeline execution finished!"

# Database operations
db-connect: ## Connect to PostgreSQL database
	docker-compose exec postgres psql -U taxi_user -d nyc_taxi

db-query-facts: ## Query fact table
	docker-compose exec postgres psql -U taxi_user -d nyc_taxi -c \
		"SELECT COUNT(*) as total_trips, AVG(fare_amount) as avg_fare, SUM(total_amount) as total_revenue FROM fact_taxi_trips;"

db-query-summary: ## Query daily summary
	docker-compose exec postgres psql -U taxi_user -d nyc_taxi -c \
		"SELECT date, pickup_borough, trip_count, avg_fare, total_revenue FROM mv_daily_trip_summary ORDER BY date DESC LIMIT 10;"

db-reset: ## Reset database (drop and recreate all tables)
	docker-compose exec postgres psql -U taxi_user -d nyc_taxi -f /docker-entrypoint-initdb.d/02-schema.sql

# CI/CD simulation
ci-lint: lint ## Run CI linting checks

ci-test: test ## Run CI tests

ci-terraform: terraform-validate ## Run CI Terraform checks

ci-build: build ## Run CI Docker build

ci-all: ci-lint ci-test ci-terraform ci-build ## Run all CI checks
	@echo "All CI checks passed!"

# Development helpers
dev-setup: ## Set up development environment
	pip install -r spark/requirements.txt
	pre-commit install || echo "pre-commit not available"

shell-spark: ## Open shell in Spark container
	docker-compose exec spark-master /bin/bash

shell-postgres: ## Open shell in PostgreSQL container
	docker-compose exec postgres /bin/bash

# Example usage targets
example-single-month: up ## Run pipeline for single month (January 2023)
	@make run-pipeline YEAR=2023 MONTHS=1

example-multi-month: up ## Run pipeline for multiple months (Jan-Mar 2023)
	@make run-pipeline YEAR=2023 MONTHS=1,2,3

example-backfill-2023: up ## Backfill all of 2023
	@make run-pipeline YEAR=2023 MONTHS=1,2,3,4,5,6,7,8,9,10,11,12