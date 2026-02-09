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
}

variable "ilb_cidr" {
  description = "CIDR for internal load balancers"
  type        = string
  default     = ""
}

variable "master_cidr" {
  description = "CIDR for Kubernetes master"
  type        = string
  default     = ""
}

variable "pod_cidr" {
  description = "Secondary range for pods"
  type        = string
  default     = ""
}

variable "service_cidr" {
  description = "Secondary range for services"
  type        = string
  default     = ""
}
