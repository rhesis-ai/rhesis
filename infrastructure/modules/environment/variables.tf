# Environment settings
variable "environment" {
  description = "Environment name (dev, prd, stg)"
  type        = string
}

variable "environment_short" {
  description = "Short environment name (dev, prd, stg)"
  type        = string
}

variable "region" {
  description = "The GCP region to deploy resources"
  type        = string
  default     = "europe-west4"
}

# Project settings
variable "billing_account" {
  description = "The billing account ID to associate with the project"
  type        = string
}

variable "org_id" {
  description = "The ID of the GCP organization (required if folder_id is not provided)"
  type        = string
  default     = ""
}

variable "folder_id" {
  description = "The ID of the GCP folder to create the project in (optional)"
  type        = string
  default     = ""
}

variable "terraform_service_account" {
  description = "The email of the service account running Terraform (for granting necessary permissions)"
  type        = string
  default     = ""
}

# Network settings
variable "subnet_cidr_range" {
  description = "CIDR range for the main subnet"
  type        = string
  default     = "10.0.0.0/20"
}

# Database settings
variable "database_password" {
  description = "The password for the database user"
  type        = string
  sensitive   = true
}

variable "db_machine_type" {
  description = "The machine type for the database instance"
  type        = string
  default     = "db-g1-small"
}

variable "db_high_availability" {
  description = "Whether to enable high availability for the database"
  type        = bool
  default     = false
}

variable "db_disk_size" {
  description = "The disk size for the database in GB"
  type        = number
  default     = 10
}

# Database connectivity settings
variable "public_ip" {
  description = "Whether to enable public IP for the database instance"
  type        = bool
  default     = true
}

# Container images
variable "backend_image" {
  description = "Container image for the backend service"
  type        = string
}

variable "frontend_image" {
  description = "Container image for the frontend service"
  type        = string
}

variable "worker_image" {
  description = "Container image for the worker service"
  type        = string
}

variable "polyphemus_image" {
  description = "Container image for the polyphemus service"
  type        = string
}

# Backend service settings
variable "backend_cpu" {
  description = "CPU allocation for the backend service"
  type        = string
  default     = "1"
}

variable "backend_memory" {
  description = "Memory allocation for the backend service"
  type        = string
  default     = "512Mi"
}

variable "backend_min_instances" {
  description = "Minimum number of instances for the backend service"
  type        = number
  default     = 0
}

variable "backend_max_instances" {
  description = "Maximum number of instances for the backend service"
  type        = number
  default     = 10
}

# Frontend service settings
variable "frontend_cpu" {
  description = "CPU allocation for the frontend service"
  type        = string
  default     = "1"
}

variable "frontend_memory" {
  description = "Memory allocation for the frontend service"
  type        = string
  default     = "512Mi"
}

variable "frontend_min_instances" {
  description = "Minimum number of instances for the frontend service"
  type        = number
  default     = 0
}

variable "frontend_max_instances" {
  description = "Maximum number of instances for the frontend service"
  type        = number
  default     = 10
}

# Worker service settings
variable "worker_cpu" {
  description = "CPU allocation for the worker service"
  type        = string
  default     = "1"
}

variable "worker_memory" {
  description = "Memory allocation for the worker service"
  type        = string
  default     = "1Gi"
}

variable "worker_min_instances" {
  description = "Minimum number of instances for the worker service"
  type        = number
  default     = 1
}

variable "worker_max_instances" {
  description = "Maximum number of instances for the worker service"
  type        = number
  default     = 5
}

# Polyphemus service settings
variable "polyphemus_cpu" {
  description = "CPU allocation for the polyphemus service"
  type        = string
  default     = "4"
}

variable "polyphemus_memory" {
  description = "Memory allocation for the polyphemus service"
  type        = string
  default     = "16Gi"
}

variable "polyphemus_min_instances" {
  description = "Minimum number of instances for the polyphemus service"
  type        = number
  default     = 0
}

variable "polyphemus_max_instances" {
  description = "Maximum number of instances for the polyphemus service"
  type        = number
  default     = 1
}

variable "polyphemus_gpu" {
  description = "GPU configuration for the polyphemus service"
  type = object({
    count = number
    type  = string
  })
  default = {
    count = 1
    type  = "nvidia-t4"
  }
}

variable "polyphemus_port" {
  description = "Port the polyphemus container listens on"
  type        = number
  default     = 8080
}

variable "polyphemus_timeout" {
  description = "Maximum time a request can take before timing out for polyphemus service"
  type        = number
  default     = 3600
}

# Default configurations
variable "service_defaults" {
  description = "Default service configurations by environment"
  type = map(object({
    db = object({
      machine_type      = string
      high_availability = bool
      disk_size         = number
    })
    backend = object({
      cpu           = string
      memory        = string
      min_instances = number
      max_instances = number
    })
    frontend = object({
      cpu           = string
      memory        = string
      min_instances = number
      max_instances = number
    })
    worker = object({
      cpu           = string
      memory        = string
      min_instances = number
      max_instances = number
    })
    polyphemus = object({
      cpu           = string
      memory        = string
      min_instances = number
      max_instances = number
    })
  }))
  default = {}
}

# Common IAM roles
variable "service_roles" {
  description = "IAM roles to assign to each service"
  type = object({
    backend    = list(string)
    frontend   = list(string)
    worker     = list(string)
    polyphemus = list(string)
    chatbot    = optional(list(string), [])
  })
  default = {
    backend    = []
    frontend   = []
    worker     = []
    polyphemus = []
    chatbot    = []
  }
}

# Common labels
variable "common_labels" {
  description = "Common labels to apply to all resources"
  type        = map(string)
  default     = {}
}

# Chatbot service settings
variable "chatbot_image" {
  description = "Container image for the chatbot service"
  type        = string
}

variable "chatbot_cpu" {
  description = "CPU allocation for the chatbot service"
  type        = string
  default     = "2"
}

variable "chatbot_memory" {
  description = "Memory allocation for the chatbot service"
  type        = string
  default     = "2Gi"
}

variable "chatbot_min_instances" {
  description = "Minimum number of instances for the chatbot service"
  type        = number
  default     = 0
}

variable "chatbot_max_instances" {
  description = "Maximum number of instances for the chatbot service"
  type        = number
  default     = 5
}

# Load balancer domain settings
variable "enable_load_balancers" {
  description = "Whether to enable load balancers for services"
  type        = bool
  default     = true
}

variable "backend_domain" {
  description = "Domain for the backend service"
  type        = string
  default     = ""
}

variable "frontend_domain" {
  description = "Domain for the frontend service"
  type        = string
  default     = ""
}

variable "worker_domain" {
  description = "Domain for the worker service"
  type        = string
  default     = ""
}

variable "polyphemus_domain" {
  description = "Domain for the polyphemus service"
  type        = string
  default     = ""
}

variable "chatbot_domain" {
  description = "Domain for the chatbot service"
  type        = string
  default     = ""
}

variable "google_application_credentials" {
  description = "Path to Google Application Credentials file"
  type        = string
  default     = ""
}

# Deployment stage control
variable "deployment_stage" {
  description = "Deployment stage (project, services, all)"
  type        = string
  default     = "all"
}

variable "create_sql_users" {
  description = "Whether to create SQL users (set to false for project-only deployment)"
  type        = bool
  default     = true
}

variable "create_service_account" {
  description = "Whether to create service accounts or use existing ones"
  type        = bool
  default     = true
} 