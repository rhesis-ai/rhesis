variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "vpc_name" {
  description = "VPC name (from network module)"
  type        = string
}

variable "nodes_subnet_self_link" {
  description = "Self link of the nodes subnet (from network module)"
  type        = string
}

variable "master_cidr" {
  description = "CIDR for GKE control plane (must match network module master subnet)"
  type        = string
  validation {
    condition     = can(cidrhost(var.master_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.2.4.0/28)."
  }
}

variable "node_cidr" {
  description = "CIDR for worker nodes (for firewall rules)"
  type        = string
  validation {
    condition     = can(cidrhost(var.node_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.2.0.0/23)."
  }
}

variable "pod_cidr" {
  description = "CIDR for pods (for firewall rules)"
  type        = string
  validation {
    condition     = can(cidrhost(var.pod_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.3.0.0/17)."
  }
}

variable "service_cidr" {
  description = "CIDR for services (for firewall rules)"
  type        = string
  validation {
    condition     = can(cidrhost(var.service_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.3.128.0/20)."
  }
}

variable "pod_range_name" {
  description = "Secondary range name for pods in the nodes subnet"
  type        = string
  default     = "pods"
}

variable "service_range_name" {
  description = "Secondary range name for services in the nodes subnet"
  type        = string
  default     = "services"
}

variable "wireguard_cidr" {
  description = "WireGuard VPN CIDR for master authorized networks"
  type        = string
  validation {
    condition     = can(cidrhost(var.wireguard_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.0.0.0/24)."
  }
}

variable "extra_authorized_cidrs" {
  description = "Additional CIDRs allowed to access the GKE master (e.g. WireGuard server env NIC IPs)"
  type        = list(string)
  default     = []
}

variable "release_channel" {
  description = "GKE release channel (STABLE, REGULAR, RAPID)"
  type        = string
  default     = "STABLE"
}

variable "machine_type" {
  description = "GCE machine type for node pool"
  type        = string
  default     = "e2-medium"
}

variable "min_node_count" {
  description = "Minimum number of nodes in the pool"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "Maximum number of nodes in the pool"
  type        = number
  default     = 3
}

variable "disk_size_gb" {
  description = "Size of the disk attached to each node (GB)"
  type        = number
  default     = 50
}

variable "disk_type" {
  description = "Type of the disk attached to each node"
  type        = string
  default     = "pd-standard"
}

variable "deletion_protection" {
  description = "Enable deletion protection on the cluster"
  type        = bool
  default     = false
}
