output "project_id" {
  description = "The ID of the GCP project"
  value       = module.dev_environment.project_id
}

output "backend_url" {
  description = "The URL of the backend service"
  value       = module.dev_environment.backend_url
}

output "frontend_url" {
  description = "The URL of the frontend service"
  value       = module.dev_environment.frontend_url
}

output "database_connection_name" {
  description = "The connection name of the database instance"
  value       = module.dev_environment.database_connection_name
}

output "artifacts_bucket" {
  description = "The name of the artifacts bucket"
  value       = module.dev_environment.artifacts_bucket
}

output "uploads_bucket" {
  description = "The name of the uploads bucket"
  value       = module.dev_environment.uploads_bucket
}

output "worker_static_ip" {
  description = "The static IP address for the worker"
  value       = module.dev_environment.worker_static_ip
} 