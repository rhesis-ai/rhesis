output "gateway_ip" {
  description = "Internal IP of the gateway VM"
  value       = google_compute_instance.gateway.network_interface[0].network_ip
}

output "gateway_instance_self_link" {
  description = "Self link of the gateway VM instance"
  value       = google_compute_instance.gateway.self_link
}

output "route_name" {
  description = "Name of the custom route created for the GKE master CIDR"
  value       = google_compute_route.master_via_gateway.name
}
