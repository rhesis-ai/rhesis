variable "project_id" {
  description = "GCP project the provider bills API calls to and that holds the state bucket (rhesis-platform-admin)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "state_bucket" {
  description = "Name of the GCS bucket holding every env's Terraform state"
  type        = string
  default     = "rhesis-platform-admin-tfstate"
}

variable "noncurrent_versions_to_keep" {
  description = "How many superseded state versions to retain once versioning is on. State objects are tiny, so keep enough to roll back several bad applies."
  type        = number
  default     = 20
}

variable "noncurrent_version_age_days" {
  description = "Also delete a superseded version this many days after it stops being current, regardless of count, so old versions do not accumulate forever."
  type        = number
  default     = 180
}

# Each terraform SA writes only its own env's state prefix and reads only the prefixes
# its root actually consumes via terraform_remote_state. The read edges are derived from
# the data.terraform_remote_state blocks in the env roots:
#   dev  -> wireguard
#   stg  -> wireguard, prd
#   wireguard -> dev, stg, prd   (and writes billing + this admin-state prefix)
# terraform-wireguard is the admin SA; it manages the bucket itself, so it holds
# storage.admin on the bucket rather than per-prefix object grants.
variable "terraform_service_accounts" {
  description = "Per-env Terraform runner service account emails, keyed by env name."
  type = object({
    dev       = string
    stg       = string
    prd       = string
    wireguard = string
  })
  default = {
    dev       = "terraform-dev@rhesis-dev-494712.iam.gserviceaccount.com"
    stg       = "terraform-stg@rhesis-stg-494712.iam.gserviceaccount.com"
    prd       = "terraform-prd@rhesis-prd.iam.gserviceaccount.com"
    wireguard = "terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com"
  }
}

variable "state_prefix_base" {
  description = "Common object-path prefix under which every env keeps its state."
  type        = string
  default     = "terraform/infrastructure/envs"
}
