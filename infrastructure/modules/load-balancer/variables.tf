variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The region where the Cloud Run service is deployed"
  type        = string
}

variable "service_name" {
  description = "Name of the service (used for naming resources)"
  type        = string
}

variable "cloud_run_service_name" {
  description = "The name of the Cloud Run service to connect to the load balancer"
  type        = string
}

variable "domain" {
  description = "The domain name to use for the SSL certificate"
  type        = string
}

variable "labels" {
  description = "Labels to apply to the load balancer resources"
  type        = map(string)
  default     = {}
}

variable "api_services_dependency" {
  description = "Dependency to ensure all needed APIs are enabled before creating load balancer resources"
  type        = any
  default     = null
} 