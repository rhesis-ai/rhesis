output "internal_lb_ip" {
  description = "Reserved internal IP for the ingress-nginx-internal load balancer"
  value       = google_compute_address.ingress_internal.address
}
