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

variable "state_bucket" {
  description = "GCS bucket holding all env Terraform states (used to read wireguard remote state)"
  type        = string
  default     = "rhesis-platform-admin-tfstate"
}


# Read by tf-setup from Secret Manager (cloudflare-rules-token-prd) into
# TF_VAR_cloudflare_rules_api_token. Ephemeral so it is kept out of state and
# the saved plan; the apply job re-reads it, which ephemeral values require.
variable "cloudflare_rules_api_token" {
  description = "Cloudflare API token for provider cloudflare.rules (Zone:Read + Config Rules:Edit on rhesis.ai)"
  type        = string
  sensitive   = true
  ephemeral   = true
}
