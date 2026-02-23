variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "vpc_name" {
  description = "VPC network name where the gateway VM is deployed"
  type        = string
}

variable "subnet_self_link" {
  description = "Self link of the subnet to place the gateway VM in"
  type        = string
}

variable "gateway_ip" {
  description = "Static internal IP for the gateway VM (must be within the subnet CIDR)"
  type        = string
  validation {
    condition     = can(regex("^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$", var.gateway_ip))
    error_message = "Must be a valid IPv4 address."
  }
}

variable "master_cidr" {
  description = "GKE control-plane master CIDR to expose via custom route"
  type        = string
  validation {
    condition     = can(cidrhost(var.master_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.2.4.0/28)."
  }
}
