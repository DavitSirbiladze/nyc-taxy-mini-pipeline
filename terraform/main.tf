# terraform/main.tf
# Main configuration file - Provider setup and core resources

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# BigQuery Dataset for Analytics
resource "google_bigquery_dataset" "nyc_taxi_analytics" {
  dataset_id                  = "nyc_taxi_analytics"
  friendly_name               = "NYC Taxi Analytics Dataset"
  description                 = "Analytics-ready dataset for NYC Taxi trip data"
  location                    = var.region
  default_table_expiration_ms = null

  labels = {
    environment = var.environment
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}

# Optional: Cloud Composer (Airflow) Environment
resource "google_composer_environment" "pipeline_orchestrator" {
  count = var.enable_composer ? 1 : 0

  name   = "nyc-taxi-pipeline-composer"
  region = var.region

  config {
    software_config {
      image_version = "composer-2-airflow-2"

      pypi_packages = {
        apache-airflow-providers-google       = ""
        apache-airflow-providers-apache-spark = ""
      }
    }

    node_config {
      service_account = google_service_account.pipeline_sa.email
    }
  }

  labels = {
    environment = var.environment
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}
