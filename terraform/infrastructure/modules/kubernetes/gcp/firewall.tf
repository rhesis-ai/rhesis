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

# Nodes to master (egress: only destination_ranges is valid)
resource "google_compute_firewall" "gke_nodes_to_master" {
  name        = "gke-nodes-to-master-${var.environment}"
  network     = var.vpc_name
  project     = var.project_id
  priority    = 900
  direction   = "EGRESS"

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  destination_ranges = [var.master_cidr]
  target_tags        = ["gke-${var.environment}"]
}

# WireGuard to master (kubectl from VPN). destination_ranges is invalid for INGRESS;
# API access is also restricted by GKE master authorized networks.
resource "google_compute_firewall" "gke_wireguard_to_master" {
  name     = "gke-wireguard-to-master-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = [var.wireguard_cidr]
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

# WireGuard to nodes and ILB (for debugging, node SSH, etc.)
resource "google_compute_firewall" "gke_wireguard_to_nodes" {
  name     = "gke-wireguard-to-nodes-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 100

  allow {
    protocol = "tcp"
  }

  allow {
    protocol = "udp"
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.wireguard_cidr]
}
