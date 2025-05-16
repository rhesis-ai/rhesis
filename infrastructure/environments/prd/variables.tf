variable "region" {
  description = "The GCP region to deploy resources"
  type        = string
  default     = "europe-west4"
}

variable "billing_account" {
  description = "The billing account ID to associate with the project"
  type        = string
}

variable "database_password" {
  description = "The password for the database user"
  type        = string
  sensitive   = true
}

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

variable "chatbot_image" {
  description = "Container image for the chatbot service"
  type        = string
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
  default     = "api.rhesis.ai"
}

variable "frontend_domain" {
  description = "Domain for the frontend service"
  type        = string
  default     = "app.rhesis.ai"
}

variable "worker_domain" {
  description = "Domain for the worker service"
  type        = string
  default     = ""
}

variable "polyphemus_domain" {
  description = "Domain for the polyphemus service"
  type        = string
  default     = "llm.rhesis.ai"
}

variable "chatbot_domain" {
  description = "Domain for the chatbot service"
  type        = string
  default     = "chat.rhesis.ai"
}

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

variable "public_ip" {
  description = "Whether to enable public IP for the database instance"
  type        = bool
  default     = true
}

variable "org_id" {
  description = "The organization ID to create the project in"
  type        = string
  default     = ""
}

variable "folder_id" {
  description = "The folder ID to create the project in"
  type        = string
  default     = ""
}

variable "terraform_service_account" {
  description = "The service account email used by Terraform to deploy resources"
  type        = string
}

variable "service_defaults" {
  description = "Default settings for services"
  type        = map(any)
  default     = {}
}

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

variable "common_labels" {
  description = "Common labels to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "google_application_credentials" {
  description = "Path to the Google Cloud service account key file"
  type        = string
  default     = ""
} 