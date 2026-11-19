variable "project_id" {
  description = "GCP project ID for the target environment."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd)."
  type        = string
  validation {
    condition     = contains(["dev", "stg", "prd"], var.environment)
    error_message = "Environment must be one of: dev, stg, prd."
  }
}

variable "membership_id" {
  description = "Fleet membership ID of the environment's cluster (module.connect_gateway_<env>.membership_id)."
  type        = string
}

variable "github_wif_pool_name" {
  description = "Resource name of the shared GitHub Actions pool (envs/wireguard output github_wif_pool_name)."
  type        = string
}

variable "repository" {
  description = "GitHub repository allowed to impersonate the account, as owner/name."
  type        = string
  default     = "rhesis-ai/rhesis"
}

variable "registry_writer" {
  description = "Let this account push to the project's `rhesis` Artifact Registry repo. Only prd sets it: the release copies the stg-tested images there."
  type        = bool
  default     = false
}

variable "registry_location" {
  description = "Location of the `rhesis` Artifact Registry repo."
  type        = string
  default     = "europe-west4"
}
