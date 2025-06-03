variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The region to deploy the service"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "service_name" {
  description = "Name of the service"
  type        = string
}

variable "container_image" {
  description = "Container image to deploy"
  type        = string
}

variable "environment_variables" {
  description = "Environment variables to set on the service"
  type        = map(string)
  default     = {}
}

variable "secret_environment_variables" {
  description = "Secret environment variables from Secret Manager"
  type        = map(object({
    secret_name = string
    secret_key  = string
  }))
  default     = {}
}

variable "iam_roles" {
  description = "IAM roles to assign to the service account"
  type        = list(string)
  default     = []
}

variable "cpu" {
  description = "CPU allocation for the service"
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Memory allocation for the service"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "allow_public_access" {
  description = "Whether to allow public access to the service"
  type        = bool
  default     = false
}

variable "custom_domain" {
  description = "Custom domain to map to the service"
  type        = string
  default     = ""
}

variable "labels" {
  description = "Labels to apply to the service"
  type        = map(string)
  default     = {}
}

variable "cloudsql_instances" {
  description = "List of Cloud SQL instance connection names to connect to the service"
  type        = list(string)
  default     = []
}

variable "port" {
  description = "Port the container listens on"
  type        = number
  default     = 8080
}

variable "container_concurrency" {
  description = "Maximum number of concurrent requests per container"
  type        = number
  default     = 80
}

variable "timeout_seconds" {
  description = "Maximum time a request can take before timing out"
  type        = number
  default     = 300
}

variable "gpu" {
  description = "GPU configuration for Cloud Run service"
  type = object({
    type  = string
    count = number
  })
  default = null
}

variable "api_services_dependency" {
  description = "Dependency to ensure all needed APIs are enabled before creating Cloud Run resources"
  type        = any
  default     = null
}

variable "create_service_account" {
  description = "Whether to create the service account or use an existing one"
  type        = bool
  default     = true
} 