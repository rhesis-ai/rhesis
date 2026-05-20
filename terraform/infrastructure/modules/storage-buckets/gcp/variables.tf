variable "project_id" {
  type        = string
  description = "GCP project ID that owns the buckets"
}

variable "environment" {
  type        = string
  description = "Short environment name: dev, stg, or prd"
}

variable "location" {
  type        = string
  description = "GCS location (e.g. europe-west4) — must match project region for regional buckets"
}

variable "file_storage_bucket_name" {
  type        = string
  description = "Globally unique GCS bucket name for backend file storage. Match STORAGE_SERVICE_URI in secrets (name only, no gs://)."
}

variable "cnpg_backup_bucket_name" {
  type        = string
  nullable    = true
  default     = null
  description = "Optional second bucket for CloudNativePG backups. Set to null/empty in dev; set for stg and prd."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Extra labels to merge onto both buckets"
}

variable "force_destroy" {
  type        = bool
  default     = false
  description = "If true, Terraform can delete non-empty buckets (use with care)"
}

variable "file_storage_iam_members" {
  type = list(object({
    member = string
    role   = string
  }))
  default     = []
  description = "Optional IAM bindings on the file storage bucket, e.g. objectAdmin for the app storage service account"
}

variable "cnpg_backup_iam_members" {
  type = list(object({
    member = string
    role   = string
  }))
  default     = []
  description = "Optional IAM bindings on the CNPG backup bucket"
}
