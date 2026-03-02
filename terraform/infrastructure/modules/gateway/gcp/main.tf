terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# Minimal gateway VM. This VM does NOT forward any traffic.
# It exists solely so that GCP treats the custom route below as valid and
# exports it via VPC peering to the WireGuard VPC.
#
# Packet flow after this fix:
#   Local → WireGuard VPC → (custom route exported via peering) → env VPC
#   → GKE peering route (priority 0, always wins) → GKE master VPC ✓
resource "google_compute_instance" "gateway" {
  name         = "gateway-${var.environment}"
  machine_type = "e2-micro"
  zone         = "${var.region}-a"
  project      = var.project_id

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet_self_link
    network_ip = var.gateway_ip
    # No access_config block = no external IP
  }

  # can_ip_forward intentionally omitted (defaults false).
  # This VM never actually routes packets; the GKE peering route (priority 0)
  # always takes precedence over the custom route (priority 1000).

  tags = ["gateway-vm"]

  metadata = {
    enable-oslogin = "TRUE"
  }

  deletion_protection = false
}

# Custom static route: dest = GKE master CIDR, next_hop = gateway VM IP.
# GCP only exports custom routes (with a VM next-hop) via peering — NOT
# routes learned from another peering (the GKE control-plane peering).
# This route is what makes the master CIDR reachable from WireGuard VPC.
resource "google_compute_route" "master_via_gateway" {
  name        = "route-gke-master-${var.environment}"
  project     = var.project_id
  network     = var.vpc_name
  dest_range  = var.master_cidr
  priority    = 1000
  next_hop_ip = var.gateway_ip

  description = "Exposes GKE master CIDR via peering to WireGuard VPC (actual forwarding by GKE peering at priority 0)"

  depends_on = [google_compute_instance.gateway]
}
