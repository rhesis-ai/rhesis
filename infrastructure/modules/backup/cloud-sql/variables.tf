variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The region to deploy the Cloud SQL instance"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "database_version" {
  description = "The database version to use"
  type        = string
  default     = "POSTGRES_14"
}

variable "machine_type" {
  description = "The machine type for the database instance"
  type        = string
  default     = "db-g1-small"
}

variable "high_availability" {
  description = "Whether to enable high availability"
  type        = bool
  default     = false
}

variable "disk_size" {
  description = "The disk size in GB"
  type        = number
  default     = 10
}

variable "disk_type" {
  description = "The disk type (PD_SSD or PD_HDD)"
  type        = string
  default     = "PD_SSD"
}

variable "enable_backups" {
  description = "Whether to enable backups"
  type        = bool
  default     = true
}

variable "enable_binary_logging" {
  description = "Whether to enable binary logging"
  type        = bool
  default     = false
}

variable "public_ip" {
  description = "Whether to enable public IP"
  type        = bool
  default     = false
}

variable "private_network_id" {
  description = "The VPC network ID for private IP"
  type        = string
  default     = ""
}

variable "authorized_networks" {
  description = "Map of authorized networks for public access"
  type        = map(string)
  default     = {}
}

variable "max_connections" {
  description = "Maximum number of database connections"
  type        = number
  default     = 100
}

variable "database_name" {
  description = "The name of the database to create"
  type        = string
}

variable "database_user" {
  description = "The name of the database user to create"
  type        = string
}

variable "database_password" {
  description = "The password for the database user"
  type        = string
  sensitive   = true
}

variable "deletion_protection" {
  description = "Whether to enable deletion protection"
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels to apply to the Cloud SQL instance"
  type        = map(string)
  default     = {}
}

variable "api_services_dependency" {
  description = "Dependency to ensure all needed APIs are enabled before creating Cloud SQL resources"
  type        = any
  default     = null
}

variable "backup_enabled" {
  description = "Whether to enable backups (alias for enable_backups)"
  type        = bool
  default     = true
  nullable    = true
}

variable "binary_log_enabled" {
  description = "Whether to enable binary logging (alias for enable_binary_logging)"
  type        = bool
  default     = false
  nullable    = true
}

variable "backup_start_time" {
  description = "Time when the backup should start (format: HH:MM)"
  type        = string
  default     = "02:00"
}

variable "private_network" {
  description = "The VPC network for private IP"
  type        = string
  default     = ""
}

variable "require_ssl" {
  description = "Whether to require SSL connections"
  type        = bool
  default     = false
}

variable "allocated_ip_range" {
  description = "The name of the allocated IP range for the private IP"
  type        = string
  default     = ""
}

variable "google_application_credentials" {
  description = "Path to the service account key file for gcloud provisioners."
  type        = string
  default     = ""
} 