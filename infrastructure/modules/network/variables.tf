variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "subnets" {
  description = "Map of subnet configurations"
  type = map(object({
    cidr_range = string
    region     = string
  }))
  default = {}
}

variable "create_nat" {
  description = "Whether to create Cloud NAT resources"
  type        = bool
  default     = true
}

variable "nat_regions" {
  description = "Map of regions for Cloud NAT"
  type        = map(string)
  default     = {}
}

variable "static_ips" {
  description = "Map of static IP configurations"
  type = map(object({
    region       = string
    address_type = string
  }))
  default = {}
} 