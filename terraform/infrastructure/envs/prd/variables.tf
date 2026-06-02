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
  default     = true
}

variable "file_storage_bucket_name" {
  description = "GCS bucket name for Rhesis backend file storage"
  type        = string
  default     = "sources-files-rhesis-prd"
}

variable "cnpg_backup_bucket_name" {
  description = "GCS bucket name for CloudNativePG Barman backups"
  type        = string
  default     = "cnpg-backup-rhesis-prd"
}

variable "force_destroy" {
  description = "Allow bucket destruction even when non-empty (must stay false for prd)"
  type        = bool
  default     = false
}

variable "bastion_iap_members" {
  description = "IAM members that can IAP-tunnel into the bastion (e.g. user:foo@example.com)"
  type        = list(string)
  default     = []
}

