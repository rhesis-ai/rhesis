output "project_id" {
  description = "The ID of the GCP project"
  value       = module.project.project_id
}

output "container_registry_url" {
  description = "The URL of the container registry"
  value       = module.container_registry.repository_url
}

output "backend_url" {
  description = "The URL of the backend service"
  value       = module.backend.service_url
}

output "frontend_url" {
  description = "The URL of the frontend service"
  value       = module.frontend.service_url
}

output "worker_url" {
  description = "The URL of the worker service"
  value       = module.worker.service_url
}

output "polyphemus_url" {
  description = "The URL of the polyphemus service"
  value       = module.polyphemus.service_url
}

output "chatbot_url" {
  description = "The URL of the chatbot service"
  value       = module.chatbot.service_url
}

# Load balancer outputs
output "backend_lb_ip" {
  description = "The static IP address for the backend load balancer"
  value       = length(module.backend_lb) > 0 ? module.backend_lb[0].static_ip : null
}

output "frontend_lb_ip" {
  description = "The static IP address for the frontend load balancer"
  value       = length(module.frontend_lb) > 0 ? module.frontend_lb[0].static_ip : null
}

output "worker_lb_ip" {
  description = "The static IP address for the worker load balancer"
  value       = length(module.worker_lb) > 0 ? module.worker_lb[0].static_ip : null
}

output "polyphemus_lb_ip" {
  description = "The static IP address for the polyphemus load balancer"
  value       = length(module.polyphemus_lb) > 0 ? module.polyphemus_lb[0].static_ip : null
}

output "chatbot_lb_ip" {
  description = "The static IP address for the chatbot load balancer"
  value       = length(module.chatbot_lb) > 0 ? module.chatbot_lb[0].static_ip : null
}

output "backend_lb_url" {
  description = "The HTTPS URL for the backend load balancer"
  value       = length(module.backend_lb) > 0 ? module.backend_lb[0].https_url : null
}

output "frontend_lb_url" {
  description = "The HTTPS URL for the frontend load balancer"
  value       = length(module.frontend_lb) > 0 ? module.frontend_lb[0].https_url : null
}

output "worker_lb_url" {
  description = "The HTTPS URL for the worker load balancer"
  value       = length(module.worker_lb) > 0 ? module.worker_lb[0].https_url : null
}

output "polyphemus_lb_url" {
  description = "The HTTPS URL for the polyphemus load balancer"
  value       = length(module.polyphemus_lb) > 0 ? module.polyphemus_lb[0].https_url : null
}

output "chatbot_lb_url" {
  description = "The HTTPS URL for the chatbot load balancer"
  value       = length(module.chatbot_lb) > 0 ? module.chatbot_lb[0].https_url : null
}

output "database_connection_name" {
  description = "The connection name of the database instance"
  value       = module.database.instance_connection_name
}

output "artifacts_bucket" {
  description = "The name of the artifacts bucket"
  value       = module.artifacts_bucket.bucket_name
}

output "uploads_bucket" {
  description = "The name of the uploads bucket"
  value       = module.uploads_bucket.bucket_name
}

output "sources_bucket" {
  description = "The name of the sources bucket"
  value       = module.sources_bucket.bucket_name
}

output "worker_static_ip" {
  description = "The static IP address for the worker"
  value       = module.network.static_ip_addresses["worker"]
}
