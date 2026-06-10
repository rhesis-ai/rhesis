variable "project_id" {
  description = "GCP project ID for the target environment."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd). Used as a prefix for Secret Manager secret IDs."
  type        = string
  validation {
    condition     = contains(["dev", "stg", "prd"], var.environment)
    error_message = "Environment must be one of: dev, stg, prd."
  }
}
