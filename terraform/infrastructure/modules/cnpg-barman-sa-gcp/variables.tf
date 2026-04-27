variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "environment" {
  type        = string
  description = "Environment name (e.g. stg, prd) — used in the service account id"
}

variable "backup_bucket_name" {
  type        = string
  description = "GCS bucket for CloudNativePG Barman backups (from storage module; must already exist)"
}

variable "secret_manager_secret_id" {
  type        = string
  description = "GSM secret name for the Barman service account JSON key; must match ExternalSecrets remoteRef.key in kubernetes/clusters/<env>/rhesis/cnpg-gcs-externalsecret.yaml"
}

