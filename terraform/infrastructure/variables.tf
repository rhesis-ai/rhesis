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

variable "wireguard_peers" {
  description = "WireGuard VPN peers with subnet access control"
  type = list(object({
    identifier = string
    ip         = string
    subnets    = list(string)
  }))
  default = []
}

