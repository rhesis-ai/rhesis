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

variable "ilb_subnet_self_link" {
  description = "Self link of the ILB subnet for internal load balancers"
  type        = string
}

variable "internal_lb_ip" {
  description = "Static private IP for the internal ingress load balancer (from ILB CIDR)"
  type        = string
}
