output "service_url" {
  description = "The URL of the deployed Cloud Run service"
  value       = google_cloud_run_service.service.status[0].url
}

output "service_name" {
  description = "The name of the deployed Cloud Run service"
  value       = google_cloud_run_service.service.name
}

output "service_id" {
  description = "The ID of the deployed Cloud Run service"
  value       = google_cloud_run_service.service.id
}

output "latest_revision_name" {
  description = "The name of the latest revision"
  value       = google_cloud_run_service.service.status[0].latest_created_revision_name
} 