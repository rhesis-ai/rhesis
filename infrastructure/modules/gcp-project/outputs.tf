output "project_id" {
  description = "The ID of the GCP project"
  value       = google_project.project.project_id
}

output "project_number" {
  description = "The number of the GCP project"
  value       = google_project.project.number
}

output "enabled_apis" {
  description = "The list of enabled APIs in the project"
  value       = google_project_service.project_services
}

output "artifact_registry_ready" {
  description = "Indicates that Artifact Registry API has been enabled"
  value       = time_sleep.wait_for_artifact_registry.id
}

output "iam_permissions_ready" {
  description = "Indicates that IAM permissions have been propagated"
  value       = time_sleep.wait_for_iam_propagation.id
  depends_on  = [
    google_project_iam_member.terraform_project_owner,
    google_project_iam_member.terraform_cloud_run_admin,
    google_project_iam_member.terraform_service_account_user,
    google_project_iam_member.terraform_artifact_registry_admin,
    google_project_iam_member.terraform_cloudsql_admin,
    google_project_iam_member.terraform_service_usage_admin,
    google_project_iam_member.terraform_project_iam_admin,
    time_sleep.wait_for_artifact_registry
  ]
}

output "compute_api_ready" {
  description = "Indicates that Compute Engine API has been enabled and is ready to use"
  value       = time_sleep.wait_for_compute_api.id
} 