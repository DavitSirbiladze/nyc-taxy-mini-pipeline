# GCS Buckets for NYC Taxi Data Pipeline
# Implements medallion architecture: Bronze, Silver, Gold zones

# Bronze Zone Bucket - Raw Data Storage
resource "google_storage_bucket" "bronze_zone" {
  name          = "${var.project_id}-nyc-taxi-bronze"
  location      = var.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  # Enable versioning for data lineage
  versioning {
    enabled = true
  }

  # Lifecycle policy to delete old data after 90 days
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  # Lifecycle policy to move to nearline after 30 days
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    environment = var.environment
    layer       = "bronze"
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}

# Silver Zone Bucket - Curated Data Storage
resource "google_storage_bucket" "silver_zone" {
  name          = "${var.project_id}-nyc-taxi-silver"
  location      = var.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  # Enable versioning for rollback capability
  versioning {
    enabled = true
  }

  # Lifecycle policy to move to coldline after 60 days
  lifecycle_rule {
    condition {
      age = 60
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = {
    environment = var.environment
    layer       = "silver"
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}

# Gold Zone Bucket - Analytics-Ready Data Storage
resource "google_storage_bucket" "gold_zone" {
  name          = "${var.project_id}-nyc-taxi-gold"
  location      = var.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  # Enable versioning
  versioning {
    enabled = true
  }

  # Keep gold data longer as it's aggregated and valuable
  lifecycle_rule {
    condition {
      age = 180
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = {
    environment = var.environment
    layer       = "gold"
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}

# Bucket for Terraform state (if using remote backend)
resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id}-terraform-state"
  location      = var.region
  force_destroy = false # Never destroy state bucket

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = false # Set to true in production
  }

  labels = {
    environment = var.environment
    purpose     = "terraform-state"
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}

# Bucket for pipeline logs
resource "google_storage_bucket" "pipeline_logs" {
  name          = "${var.project_id}-pipeline-logs"
  location      = var.region
  force_destroy = var.force_destroy

  uniform_bucket_level_access = true

  # Auto-delete logs after 30 days
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    purpose     = "logs"
    project     = "nyc-taxi-pipeline"
    managed_by  = "terraform"
  }
}
