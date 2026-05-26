variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "gke_deletion_protection" {
  description = "Enable deletion protection for GKE cluster"
  type        = bool
  default     = false
}

variable "file_storage_bucket_name" {
  description = "GCS bucket name for Rhesis backend file storage"
  type        = string
  default     = "sources-files-rhesis-stg"
}

variable "cnpg_backup_bucket_name" {
  description = "GCS bucket name for CloudNativePG Barman backups"
  type        = string
  default     = "cnpg-backup-rhesis-stg"
}

variable "force_destroy" {
  description = "Allow bucket destruction even when non-empty (set false for production data)"
  type        = bool
  default     = false
}

