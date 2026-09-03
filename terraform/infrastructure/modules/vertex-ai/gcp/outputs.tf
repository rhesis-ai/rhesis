output "service_account_email" {
  description = "Email of the per-environment Vertex AI service account; mint the key for GOOGLE_APPLICATION_CREDENTIALS against this"
  value       = google_service_account.vertex.email
}

output "project_id" {
  description = "Project the Vertex AI calls are billed to and quota-limited in"
  value       = var.project_id
}
