variable "project_id" {
  description = "GCP project ID"
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
