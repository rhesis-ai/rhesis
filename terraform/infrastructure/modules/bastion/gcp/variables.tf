variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (stg, prd)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "zone" {
  description = "GCP zone for the bastion VM"
  type        = string
}

variable "nodes_subnet_self_link" {
  description = "Self link of the nodes subnet — bastion lives here so it can reach the GKE private endpoint"
  type        = string
}

variable "vpc_name" {
  description = "VPC network name (for firewall rule)"
  type        = string
}

variable "machine_type" {
  description = "Machine type for the bastion VM"
  type        = string
  default     = "e2-micro"
}

variable "iap_members" {
  description = "IAM members that can IAP-tunnel into the bastion (e.g. user:foo@example.com)"
  type        = list(string)
  default     = []
}
