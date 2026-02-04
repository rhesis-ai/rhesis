variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The region to deploy the container registry"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "labels" {
  description = "Labels to apply to the registry"
  type        = map(string)
  default     = {}
}

variable "api_services_dependency" {
  description = "Dependency to ensure all needed APIs are enabled before creating container registry resources"
  type        = any
  default     = null
} 