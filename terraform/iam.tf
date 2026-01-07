# IAM Configuration for NYC Taxi Data Pipeline
# Service accounts and role bindings following principle of least privilege

# Service Account for Pipeline Execution
resource "google_service_account" "pipeline_sa" {
  account_id   = "nyc-taxi-pipeline-sa"
  display_name = "NYC Taxi Pipeline Service Account"
  description  = "Service account for running NYC taxi data pipeline jobs (Spark, Airflow)"
}

# Service Account for Dataproc (if using managed Spark)
resource "google_service_account" "dataproc_sa" {
  account_id   = "nyc-taxi-dataproc-sa"
  display_name = "NYC Taxi Dataproc Service Account"
  description  = "Service account for Dataproc cluster execution"
}

# IAM Role Bindings for Bronze Bucket
resource "google_storage_bucket_iam_member" "bronze_objectAdmin" {
  bucket = google_storage_bucket.bronze_zone.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_storage_bucket_iam_member" "bronze_legacyBucketReader" {
  bucket = google_storage_bucket.bronze_zone.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# IAM Role Bindings for Silver Bucket
resource "google_storage_bucket_iam_member" "silver_objectAdmin" {
  bucket = google_storage_bucket.silver_zone.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_storage_bucket_iam_member" "silver_legacyBucketReader" {
  bucket = google_storage_bucket.silver_zone.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# IAM Role Bindings for Gold Bucket
resource "google_storage_bucket_iam_member" "gold_objectAdmin" {
  bucket = google_storage_bucket.gold_zone.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_storage_bucket_iam_member" "gold_legacyBucketReader" {
  bucket = google_storage_bucket.gold_zone.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# IAM Role Bindings for Pipeline Logs Bucket
resource "google_storage_bucket_iam_member" "logs_objectAdmin" {
  bucket = google_storage_bucket.pipeline_logs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# BigQuery Role for Pipeline SA
resource "google_project_iam_member" "pipeline_bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_bigquery_dataEditor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

resource "google_project_iam_member" "pipeline_bigquery_jobUser" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Dataproc Roles (if using Dataproc)
resource "google_project_iam_member" "dataproc_worker" {
  project = var.project_id
  role    = "roles/dataproc.worker"
  member  = "serviceAccount:${google_service_account.dataproc_sa.email}"
}

resource "google_project_iam_member" "dataproc_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.dataproc_sa.email}"
}

# Service Account Key for Pipeline SA (for local/CI usage)
# Note: In production, prefer Workload Identity Federation
resource "google_service_account_key" "pipeline_key" {
  service_account_id = google_service_account.pipeline_sa.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

# Service Account Key for Dataproc SA
resource "google_service_account_key" "dataproc_key" {
  service_account_id = google_service_account.dataproc_sa.name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

# Custom IAM Role for fine-grained permissions
resource "google_project_iam_custom_role" "pipeline_custom_role" {
  role_id     = "nycTaxiPipelineRole"
  title       = "NYC Taxi Pipeline Custom Role"
  description = "Custom role with minimal permissions for NYC Taxi pipeline"

  permissions = [
    "storage.buckets.get",
    "storage.buckets.list",
    "storage.objects.create",
    "storage.objects.delete",
    "storage.objects.get",
    "storage.objects.list",
    "storage.objects.update",
    "bigquery.datasets.get",
    "bigquery.tables.create",
    "bigquery.tables.delete",
    "bigquery.tables.get",
    "bigquery.tables.getData",
    "bigquery.tables.list",
    "bigquery.tables.update",
    "bigquery.tables.updateData",
    "bigquery.jobs.create",
  ]
}

# Assign custom role to pipeline SA
resource "google_project_iam_member" "pipeline_custom_role_binding" {
  project = var.project_id
  role    = google_project_iam_custom_role.pipeline_custom_role.id
  member  = "serviceAccount:${google_service_account.pipeline_sa.email}"
}

# Best Practice Notes:
# 1. In production, use Workload Identity instead of service account keys
# 2. Rotate service account keys regularly (every 90 days)
# 3. Use separate service accounts for different environments (dev/staging/prod)
# 4. Enable audit logging for all service account activities
# 5. Use custom roles instead of primitive roles when possible
