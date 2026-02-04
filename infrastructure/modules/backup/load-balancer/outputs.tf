output "static_ip" {
  description = "The static IP address for the load balancer"
  value       = google_compute_global_address.static_ip.address
}

output "static_ip_name" {
  description = "The name of the static IP address resource"
  value       = google_compute_global_address.static_ip.name
}

output "https_url" {
  description = "The HTTPS URL for accessing the service"
  value       = "https://${var.domain}"
} 