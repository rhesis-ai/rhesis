variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (wireguard, dev, stg, prd)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "network_cidr" {
  description = "Primary network CIDR block"
  type        = string
  validation {
    condition     = can(cidrhost(var.network_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.0.0.0/24)."
  }
}

variable "create_gke_subnets" {
  description = "Create GKE-ready subnets (nodes, ilb, master, pods, services)"
  type        = bool
  default     = false
}

variable "node_cidr" {
  description = "CIDR for Kubernetes worker nodes"
  type        = string
  default     = ""
  validation {
    condition     = var.node_cidr == "" || can(cidrhost(var.node_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.2.0.0/23)."
  }
}

variable "ilb_cidr" {
  description = "CIDR for internal load balancers"
  type        = string
  default     = ""
  validation {
    condition     = var.ilb_cidr == "" || can(cidrhost(var.ilb_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.2.2.0/23)."
  }
}

variable "master_cidr" {
  description = "CIDR for Kubernetes master"
  type        = string
  default     = ""
  validation {
    condition     = var.master_cidr == "" || can(cidrhost(var.master_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.2.4.0/28)."
  }
}

variable "pod_cidr" {
  description = "Secondary range for pods"
  type        = string
  default     = ""
  validation {
    condition     = var.pod_cidr == "" || can(cidrhost(var.pod_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.3.0.0/17)."
  }
}

variable "service_cidr" {
  description = "Secondary range for services"
  type        = string
  default     = ""
  validation {
    condition     = var.service_cidr == "" || can(cidrhost(var.service_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.3.128.0/20)."
  }
}
