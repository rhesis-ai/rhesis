output "project_id" {
  description = "The ID of the GCP project"
  value       = module.stg_environment.project_id
}

output "backend_url" {
  description = "The URL of the backend service"
  value       = module.stg_environment.backend_url
}

output "frontend_url" {
  description = "The URL of the frontend service"
  value       = module.stg_environment.frontend_url
}

output "database_connection_name" {
  description = "The connection name of the database instance"
  value       = module.stg_environment.database_connection_name
}

output "artifacts_bucket" {
  description = "The name of the artifacts bucket"
  value       = module.stg_environment.artifacts_bucket
}

output "uploads_bucket" {
  description = "The name of the uploads bucket"
  value       = module.stg_environment.uploads_bucket
}

output "worker_static_ip" {
  description = "The static IP address for the worker"
  value       = module.stg_environment.worker_static_ip
} 