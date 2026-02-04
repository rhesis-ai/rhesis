output "repository_id" {
  description = "The ID of the created repository"
  value       = google_artifact_registry_repository.registry.repository_id
}

output "repository_name" {
  description = "The name of the created repository"
  value       = google_artifact_registry_repository.registry.name
}

output "repository_url" {
  description = "The URL of the created repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.registry.repository_id}"
} 