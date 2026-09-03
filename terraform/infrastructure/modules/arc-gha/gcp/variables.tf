variable "project_id" {
  description = "GCP project ID for the target environment."
  type        = string
}

variable "manage_placeholder_versions" {
  description = <<-EOT
    Create the seed placeholder versions. Only correct where Terraform created the secret in
    the first place: the placeholder is version 1 and the real value is added afterwards as
    version 2, so `latest` resolves to the real value.

    Set false where the secret already exists with the REAL value in version 1 (prd, whose
    secrets were created by hand). There, Terraform must not manage versions at all. Creating
    one would make a placeholder `latest` and ESO would sync PLACEHOLDER_* into the cluster,
    and importing the existing one is worse: secret_data is stored in Terraform state, so a
    live GitHub App private key would land in the state bucket in plaintext.
  EOT
  type        = bool
  default     = true
}

variable "environment" {
  description = "Environment name (dev, stg, prd). Used as a prefix for Secret Manager secret IDs."
  type        = string
  validation {
    condition     = contains(["dev", "stg", "prd"], var.environment)
    error_message = "Environment must be one of: dev, stg, prd."
  }
}
