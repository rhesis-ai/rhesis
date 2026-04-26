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
  type        = string
  default     = "sources-rhesis-stg"
  description = "GCS bucket for backend files. Must match STORAGE_SERVICE_URI in secrets (name only)."
}

variable "cnpg_backup_bucket_name" {
  type        = string
  default     = "cnpg-backup-rhesis-stg"
  description = "GCS bucket for CloudNativePG (Barman) backups; align with GitOps/Cluster config"
}

variable "gcs_bucket_force_destroy" {
  type        = bool
  default     = false
  description = "Allow Terraform to delete GCS buckets that still contain objects"
}

variable "file_storage_iam_members" {
  type = list(object({
    member = string
    role   = string
  }))
  default     = []
  description = "Optional IAM for the file storage bucket"
}

variable "cnpg_backup_iam_members" {
  type = list(object({
    member = string
    role   = string
  }))
  default     = []
  description = "Optional IAM for the CNPG backup bucket"
}

