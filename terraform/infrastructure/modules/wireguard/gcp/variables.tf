variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (wireguard)"
  type        = string
  default     = "wireguard"
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "vpc_name" {
  description = "VPC network name"
  type        = string
}

variable "subnet_self_link" {
  description = "Subnet self link"
  type        = string
}

variable "wireguard_tunnel_ip" {
  description = "WireGuard tunnel interface IP (wg0 address, used by VPN clients)"
  type        = string
  default     = "10.0.0.1"
  validation {
    condition     = can(regex("^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$", var.wireguard_tunnel_ip))
    error_message = "Must be a valid IPv4 address (e.g., 10.0.0.1)."
  }
}

variable "wireguard_subnet_ip" {
  description = "WireGuard VM IP in the GCP VPC subnet (primary NIC address)"
  type        = string
  default     = "10.0.0.10"
  validation {
    condition     = can(regex("^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$", var.wireguard_subnet_ip))
    error_message = "Must be a valid IPv4 address (e.g., 10.0.0.10)."
  }
}

variable "wireguard_port" {
  description = "WireGuard listen port"
  type        = number
  default     = 51820
}

variable "wireguard_peer_cidr" {
  description = "WireGuard peer CIDR range"
  type        = string
  default     = "10.0.0.0/24"
  validation {
    condition     = can(cidrhost(var.wireguard_peer_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.0.0.0/24)."
  }
}

variable "wireguard_peers" {
  description = "List of WireGuard peers with subnet access"
  type = list(object({
    identifier = string
    ip         = string
    subnets    = list(string)
  }))
}

variable "subnet_cidrs" {
  description = "Map of environment names to network CIDR blocks"
  type        = map(string)
  validation {
    condition     = alltrue([for cidr in values(var.subnet_cidrs) : can(cidrhost(cidr, 0))])
    error_message = "All values must be valid CIDR blocks."
  }
}

variable "master_cidrs" {
  description = "Map of environment to GKE master CIDR blocks"
  type        = map(string)
  validation {
    condition     = alltrue([for cidr in values(var.master_cidrs) : can(cidrhost(cidr, 0))])
    error_message = "All values must be valid CIDR blocks."
  }
}

variable "machine_type" {
  description = "VM machine type"
  type        = string
  default     = "e2-micro"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 10
}

variable "deletion_protection" {
  description = "Enable deletion protection for WireGuard server"
  type        = bool
  default     = true
}

variable "env_nics" {
  description = "Extra NICs in env VPCs for forwarding kubectl traffic to GKE master (eth1=dev, eth2=stg, eth3=prd)"
  type = list(object({
    subnet_self_link = string
    network_ip       = string
    master_cidr      = string
  }))
  default = []
}
