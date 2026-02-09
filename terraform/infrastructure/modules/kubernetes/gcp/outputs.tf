output "cluster_id" {
  description = "Cluster ID"
  value       = google_container_cluster.cluster.id
}

output "cluster_name" {
  description = "Cluster name"
  value       = google_container_cluster.cluster.name
}

output "cluster_endpoint" {
  description = "Cluster API endpoint (private)"
  value       = google_container_cluster.cluster.endpoint
}

output "cluster_ca_certificate" {
  description = "Cluster CA certificate"
  value       = google_container_cluster.cluster.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "service_account_email" {
  description = "Cluster service account email"
  value       = google_service_account.cluster.email
}
