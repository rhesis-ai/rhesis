variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd)"
  type        = string
}

variable "eso_namespace" {
  description = "Kubernetes namespace where ESO is installed"
  type        = string
  default     = "external-secrets"
}

variable "eso_service_account_name" {
  description = "Kubernetes service account name used by ESO"
  type        = string
  default     = "external-secrets"
}
