
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-central2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "enable_composer" {
  description = "Whether to create Cloud Composer environment"
  type        = bool
  default     = false
}

variable "force_destroy" {
  description = "When set to true, Terraform can destroy the storage bucket even if it contains objects"
  type        = bool
  default     = false
}
