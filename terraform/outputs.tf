# terraform/outputs.tf
# Centralized outputs for all resources

# GCS Bucket Outputs
output "bronze_bucket_name" {
  description = "Name of the bronze zone GCS bucket"
  value       = google_storage_bucket.bronze_zone.name
}

output "silver_bucket_name" {
  description = "Name of the silver zone GCS bucket"
  value       = google_storage_bucket.silver_zone.name
}

output "gold_bucket_name" {
  description = "Name of the gold zone GCS bucket"
  value       = google_storage_bucket.gold_zone.name
}

output "bronze_bucket_url" {
  description = "URL of the bronze zone bucket"
  value       = "gs://${google_storage_bucket.bronze_zone.name}"
}

output "silver_bucket_url" {
  description = "URL of the silver zone bucket"
  value       = "gs://${google_storage_bucket.silver_zone.name}"
}

output "gold_bucket_url" {
  description = "URL of the gold zone bucket"
  value       = "gs://${google_storage_bucket.gold_zone.name}"
}

output "logs_bucket_name" {
  description = "Name of the pipeline logs bucket"
  value       = google_storage_bucket.pipeline_logs.name
}

output "terraform_state_bucket_name" {
  description = "Name of the Terraform state bucket"
  value       = google_storage_bucket.terraform_state.name
}

# Service Account Outputs
output "service_account_email" {
  description = "Email of the pipeline service account"
  value       = google_service_account.pipeline_sa.email
}

output "dataproc_service_account_email" {
  description = "Email of the Dataproc service account"
  value       = google_service_account.dataproc_sa.email
}

output "service_account_key" {
  description = "Service account key (base64 encoded, sensitive)"
  value       = google_service_account_key.pipeline_key.private_key
  sensitive   = true
}

# BigQuery Outputs
output "bigquery_dataset_id" {
  description = "BigQuery dataset ID for analytics"
  value       = google_bigquery_dataset.nyc_taxi_analytics.dataset_id
}

output "bigquery_dataset_location" {
  description = "Location of the BigQuery dataset"
  value       = google_bigquery_dataset.nyc_taxi_analytics.location
}

# Composer Outputs (conditional)
output "composer_environment_name" {
  description = "Name of the Cloud Composer environment"
  value       = var.enable_composer ? google_composer_environment.pipeline_orchestrator[0].name : null
}

output "composer_airflow_uri" {
  description = "URI of the Airflow web interface"
  value       = var.enable_composer ? google_composer_environment.pipeline_orchestrator[0].config[0].airflow_uri : null
}
