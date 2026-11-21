variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd)"
  type        = string
}

variable "tsig_key_rotation" {
  description = "Rotation marker for the TSIG key. Setting or changing it generates a new key and a new Secret Manager version on the next apply; null keeps the current key."
  type        = string
  default     = null
}
