variable "project_id" {
  description = "GCP project ID for the target environment."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd). Used as a prefix for Secret Manager secret IDs."
  type        = string
}
