variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
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

