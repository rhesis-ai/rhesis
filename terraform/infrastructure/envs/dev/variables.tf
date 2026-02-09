variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "wireguard_cidr" {
  description = "WireGuard VPN CIDR for GKE master authorized networks"
  type        = string
  default     = "10.0.0.0/24"
}
