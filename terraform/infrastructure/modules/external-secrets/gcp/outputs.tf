output "service_account_email" {
  description = "ESO GCP service account email"
  value       = google_service_account.eso.email
}

output "workload_identity_provider" {
  description = "Workload Identity provider for ESO"
  value       = "${var.project_id}.svc.id.goog[${var.eso_namespace}/${var.eso_service_account_name}]"
}
