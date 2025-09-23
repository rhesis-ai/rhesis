variable "project_id" {
  description = "The ID of the GCP project"
  type        = string
}

variable "region" {
  description = "The region for the storage bucket"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prd, stg)"
  type        = string
}

variable "bucket_prefix" {
  description = "Prefix for the bucket name (usually the project name)"
  type        = string
  default     = "rhesis"
}

variable "bucket_name" {
  description = "Name of the bucket (will be combined with prefix, env, and region)"
  type        = string
}

variable "storage_class" {
  description = "Storage class for the bucket"
  type        = string
  default     = "STANDARD"
}

variable "enable_versioning" {
  description = "Whether to enable versioning for the bucket"
  type        = bool
  default     = false
}

variable "lifecycle_rule_age" {
  description = "Age in days for lifecycle rule"
  type        = number
  default     = 90
}

variable "lifecycle_rule_action" {
  description = "Action for lifecycle rule (e.g., Delete, SetStorageClass)"
  type        = string
  default     = "Delete"
}

variable "force_destroy" {
  description = "Whether to force destroy the bucket even if it contains objects"
  type        = bool
  default     = false
}

variable "iam_bindings" {
  description = "Map of role to list of members for IAM bindings"
  type        = map(list(string))
  default     = {}
}

variable "labels" {
  description = "Labels to apply to the storage bucket"
  type        = map(string)
  default     = {}
}

variable "public_access_prevention" {
  description = "Public access prevention setting"
  type        = string
  default     = "inherited"
  validation {
    condition = contains(["inherited", "enforced"], var.public_access_prevention)
    error_message = "Public access prevention must be either 'inherited' or 'enforced'."
  }
}
