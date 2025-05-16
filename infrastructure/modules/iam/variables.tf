variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "service_name" {
  description = "Name of the service for the service account"
  type        = string
}

variable "roles" {
  description = "List of IAM roles to assign to the service account"
  type        = list(string)
  default     = []
}

variable "create_key" {
  description = "Whether to create a service account key"
  type        = bool
  default     = false
}

variable "workload_identity_users" {
  description = "List of workload identity users for the service account"
  type        = list(string)
  default     = []
}

variable "create_service_account" {
  description = "Whether to create the service account or use an existing one"
  type        = bool
  default     = true
} 