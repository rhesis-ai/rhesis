variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "enabled_environments" {
  description = "Which environments to deploy (e.g. [\"dev\"] for dev-only)"
  type        = list(string)
  default     = ["dev", "stg", "prd"]

  validation {
    condition = alltrue([
      for env in var.enabled_environments : contains(["dev", "stg", "prd"], env)
    ])
    error_message = "Allowed values: dev, stg, prd."
  }
}

variable "wireguard_deletion_protection" {
  description = "Enable deletion protection for WireGuard server"
  type        = bool
  default     = true
}

variable "gke_deletion_protection" {
  description = "Enable deletion protection per GKE cluster (dev/stg typically false, prd true)"
  type = object({
    dev = bool
    stg = bool
    prd = bool
  })
  default = {
    dev = false
    stg = false
    prd = true
  }
}

variable "wireguard_peers" {
  description = "WireGuard VPN peers with subnet access control"
  type = list(object({
    identifier = string
    ip         = string
    subnets    = list(string)
  }))
  default = []
}

# GCS: backend file storage (all enabled envs) + CNPG backup buckets (stg/prd only).
# Names must match STORAGE_SERVICE_URI and CNPG backup settings in GitHub/Secret Manager.
variable "gcs" {
  description = <<-EOT
    GCS file-storage buckets for each environment. CNPG backup buckets are set only for stg and prd;
    dev does not get a backup bucket (Bitnami PostgreSQL in dev, CNPG in stg/prd).
  EOT
  type = object({
    dev = object({
      file_storage_bucket_name = string
      force_destroy            = optional(bool, false)
      file_storage_iam_members = optional(list(object({
        member = string
        role   = string
      })), [])
    })
    stg = object({
      file_storage_bucket_name = string
      cnpg_backup_bucket_name  = string
      force_destroy            = optional(bool, false)
      file_storage_iam_members = optional(list(object({
        member = string
        role   = string
      })), [])
      cnpg_backup_iam_members = optional(list(object({
        member = string
        role   = string
      })), [])
    })
    prd = object({
      file_storage_bucket_name = string
      cnpg_backup_bucket_name  = string
      force_destroy            = optional(bool, false)
      file_storage_iam_members = optional(list(object({
        member = string
        role   = string
      })), [])
      cnpg_backup_iam_members = optional(list(object({
        member = string
        role   = string
      })), [])
    })
  })
  default = {
    dev = { file_storage_bucket_name = "sources-files-rhesis-dev" }
    stg = {
      file_storage_bucket_name = "sources-files-rhesis-stg"
      cnpg_backup_bucket_name  = "cnpg-backup-rhesis-stg"
    }
    prd = {
      file_storage_bucket_name = "sources-files-rhesis-prd"
      cnpg_backup_bucket_name  = "cnpg-backup-rhesis-prd"
    }
  }
}

