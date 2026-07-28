variable "project_id" {
  description = "GCP project ID for the target environment."
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stg, prd). Used as the Fleet membership ID."
  type        = string
  validation {
    condition     = contains(["dev", "stg", "prd"], var.environment)
    error_message = "Environment must be one of: dev, stg, prd."
  }
}

variable "cluster_id" {
  description = <<-EOT
    Full resource ID of the GKE cluster to register, in the form
    "projects/{project}/locations/{location}/clusters/{name}" -- this is
    exactly what `google_container_cluster.cluster.id` (module.gke_<env>.cluster_id)
    returns.
  EOT
  type        = string
}

variable "ci_service_account_email" {
  description = <<-EOT
    Email of the service account CI workflows authenticate as (the one behind
    the GCP_SA_KEY / WIF-bound identity used by GitHub Actions). Granted
    roles/gkehub.gatewayReader so `gcloud container fleet memberships
    get-credentials` works for it without VPN access to the cluster.
  EOT
  type        = string
}
