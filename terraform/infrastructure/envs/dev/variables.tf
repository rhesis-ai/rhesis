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

# GCS: backend file storage. Name must match STORAGE_SERVICE_URI in GitHub/service secrets (e.g. gs://sources-rhesis-dev).
variable "file_storage_bucket_name" {
  type        = string
  default     = "sources-rhesis-dev"
  description = "GCS bucket for backend files (override to match your secrets; name only, no gs:// prefix)"
}

# CNPG backup bucket: not used in dev (dev uses in-cluster Bitnami PostgreSQL, not CNPG in cluster).
variable "cnpg_backup_bucket_name" {
  type        = string
  nullable    = true
  default     = null
  description = "Optional CNPG backup bucket; leave null in dev"
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
  description = "Optional IAM for the file storage bucket (e.g. service account with roles/storage.objectAdmin)"
}

variable "cnpg_backup_iam_members" {
  type = list(object({
    member = string
    role   = string
  }))
  default     = []
  description = "Optional IAM for the CNPG backup bucket (unused when cnpg_backup_bucket_name is null)"
}

