variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "terraform_state_bucket" {
  description = "GCS bucket name for storing Terraform state"
  type        = string
}

variable "wireguard_cidr" {
  description = "WireGuard network CIDR"
  type        = string
  default     = "10.0.0.0/24"
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

variable "ssh_keys" {
  description = "SSH public keys for WireGuard server (format: 'user:ssh-rsa AAAA...')"
  type        = list(string)
  default     = []
}
