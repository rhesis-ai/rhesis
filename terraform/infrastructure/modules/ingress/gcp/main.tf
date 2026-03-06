terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# Reserve a static internal IP for the internal ingress load balancer.
# GKE will assign this IP to the ingress-nginx-internal Service.
resource "google_compute_address" "ingress_internal" {
  name         = "ingress-internal-${var.environment}"
  subnetwork   = var.ilb_subnet_self_link
  address_type = "INTERNAL"
  address      = var.internal_lb_ip
  region       = var.region
  project      = var.project_id
}
