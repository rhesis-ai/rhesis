output "vpc_id" {
  description = "The ID of the VPC"
  value       = google_compute_network.vpc.id
}

output "vpc_name" {
  description = "The name of the VPC"
  value       = google_compute_network.vpc.name
}

output "vpc_self_link" {
  description = "The self link of the VPC"
  value       = google_compute_network.vpc.self_link
}

output "subnet_ids" {
  description = "Map of subnet names to their IDs"
  value       = { for k, v in google_compute_subnetwork.subnet : k => v.id }
}

output "subnet_self_links" {
  description = "Map of subnet names to their self links"
  value       = { for k, v in google_compute_subnetwork.subnet : k => v.self_link }
}

output "static_ip_addresses" {
  description = "Map of static IP names to their addresses"
  value       = { for k, v in google_compute_address.static_ip : k => v.address }
} 