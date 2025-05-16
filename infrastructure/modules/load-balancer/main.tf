terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = ">= 4.0.0"
    }
    time = {
      source = "hashicorp/time"
    }
  }
}

# Simplified approach - rely on the properly enabled Compute API from the project module
resource "google_compute_global_address" "static_ip" {
  name        = "${var.service_name}-static-ip"
  project     = var.project_id
  description = "Static IP for ${var.service_name} load balancer"
  
  labels = var.labels
  
  # Ensure this depends on the API services being enabled
  depends_on = [var.api_services_dependency]
}

resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "${var.service_name}-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.cloud_run_service_name
  }
  
  depends_on = [var.api_services_dependency]
}

resource "google_compute_backend_service" "backend" {
  name                  = "${var.service_name}-backend"
  project               = var.project_id
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }
  
  depends_on = [google_compute_region_network_endpoint_group.serverless_neg]
}

resource "google_compute_url_map" "url_map" {
  name            = "${var.service_name}-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.backend.id
  
  depends_on = [google_compute_backend_service.backend]
}

resource "google_compute_managed_ssl_certificate" "ssl_cert" {
  name     = "${var.service_name}-ssl-cert"
  project  = var.project_id
  
  managed {
    domains = [var.domain]
  }
  
  depends_on = [var.api_services_dependency]
}

resource "google_compute_target_https_proxy" "https_proxy" {
  name             = "${var.service_name}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.ssl_cert.id]
  
  depends_on = [google_compute_url_map.url_map, google_compute_managed_ssl_certificate.ssl_cert]
}

resource "google_compute_global_forwarding_rule" "forwarding_rule" {
  name                  = "${var.service_name}-forwarding-rule"
  project               = var.project_id
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "443"
  target                = google_compute_target_https_proxy.https_proxy.id
  ip_address            = google_compute_global_address.static_ip.id
  
  depends_on = [google_compute_target_https_proxy.https_proxy, google_compute_global_address.static_ip]
} 