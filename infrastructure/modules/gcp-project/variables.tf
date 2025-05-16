variable "project_name" {
  description = "The name of the GCP project"
  type        = string
}

variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

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

variable "labels" {
  description = "Labels to apply to the project"
  type        = map(string)
  default     = {}
}

variable "terraform_service_account" {
  description = "The email of the service account running Terraform (for granting necessary permissions)"
  type        = string
  default     = ""
} 