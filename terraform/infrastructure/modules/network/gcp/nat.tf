# Cloud NAT for private GKE nodes to access the internet (pull images, etc.)
# Only created when GKE subnets are enabled

resource "google_compute_router" "nat_router" {
  count = var.create_gke_subnets ? 1 : 0

  name    = "router-${var.environment}-${var.region}"
  region  = var.region
  network = google_compute_network.vpc.id
  project = var.project_id
}

resource "google_compute_router_nat" "nat" {
  count = var.create_gke_subnets ? 1 : 0

  name    = "nat-${var.environment}-${var.region}"
  router  = google_compute_router.nat_router[0].name
  region  = var.region
  project = var.project_id

  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = google_compute_subnetwork.nodes[0].id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
