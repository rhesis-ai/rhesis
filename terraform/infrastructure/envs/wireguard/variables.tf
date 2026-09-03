variable "project_id" {
  description = "GCP project ID (rhesis-platform-admin)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "network_cidr" {
  description = "WireGuard network CIDR"
  type        = string
  default     = "10.0.0.0/24"
}

variable "state_bucket" {
  description = "GCS bucket holding all env Terraform states"
  type        = string
  default     = "rhesis-platform-admin-tfstate"
}

variable "enabled_environments" {
  description = <<-EOT
    Which environments to peer with and configure BIND9 for. Defaults to everything that
    actually exists, because this list is destructive when it under-reports: anything omitted
    has its peering destroyed, its BIND9 zone dropped, and (for prd) the WireGuard VM's
    cross-project NIC removed, which forces instance recreation.

    Narrow it only for a genuine bootstrap, where an environment's remote state does not yet
    exist. All three have existed since 2026-07, so the incremental-rollout case this was
    written for is spent.
  EOT
  type        = list(string)
  default     = ["dev", "stg", "prd"]

  validation {
    condition     = alltrue([for e in var.enabled_environments : contains(["dev", "stg", "prd"], e)])
    error_message = "Allowed values: dev, stg, prd."
  }
}

variable "wireguard_deletion_protection" {
  description = "Enable deletion protection for WireGuard server. Defaults to true — the VPN server is critical infrastructure and must not be accidentally destroyed."
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
