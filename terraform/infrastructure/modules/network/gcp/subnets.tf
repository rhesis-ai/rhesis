# Wireguard: single subnet
resource "google_compute_subnetwork" "wireguard" {
  count = var.create_gke_subnets ? 0 : 1

  name                     = "subnet-${var.environment}-${var.region}"
  ip_cidr_range            = var.network_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

# Cluster envs: nodes, ilb, master subnets with secondary ranges for pods/services
resource "google_compute_subnetwork" "nodes" {
  count = var.create_gke_subnets ? 1 : 0

  name                     = "subnet-nodes-${var.environment}-${var.region}"
  ip_cidr_range            = var.node_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pod_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.service_cidr
  }

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "ilb" {
  count = var.create_gke_subnets ? 1 : 0

  name                     = "subnet-ilb-${var.environment}-${var.region}"
  ip_cidr_range            = var.ilb_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_subnetwork" "master" {
  count = var.create_gke_subnets ? 1 : 0

  name                     = "subnet-master-${var.environment}-${var.region}"
  ip_cidr_range            = var.master_cidr
  region                   = var.region
  network                  = google_compute_network.vpc.id
  project                  = var.project_id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.5
    metadata             = "INCLUDE_ALL_METADATA"
  }
}
