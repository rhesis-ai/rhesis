# GKE firewall rules (priority 900, lower than deny-all baseline at 1000)

# Master to nodes: health checks and API
resource "google_compute_firewall" "gke_master_to_nodes" {
  name     = "gke-master-to-nodes-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["443", "10250"]
  }

  source_ranges = [var.master_cidr]
  target_tags   = ["gke-${var.environment}"]
}

# Nodes to master
resource "google_compute_firewall" "gke_nodes_to_master" {
  name     = "gke-nodes-to-master-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges      = [var.node_cidr, var.pod_cidr]
  destination_ranges = [var.master_cidr]
}

# WireGuard to master (kubectl from VPN)
resource "google_compute_firewall" "gke_wireguard_to_master" {
  name     = "gke-wireguard-to-master-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges      = [var.wireguard_cidr]
  destination_ranges = [var.master_cidr]
}

# Internal cluster: nodes, pods, services
resource "google_compute_firewall" "gke_internal" {
  name     = "gke-internal-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.node_cidr, var.pod_cidr, var.service_cidr]
}
