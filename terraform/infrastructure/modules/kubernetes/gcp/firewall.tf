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
  name      = "gke-nodes-to-master-${var.environment}"
  network   = var.vpc_name
  project   = var.project_id
  priority  = 900
  direction = "EGRESS"

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
# Per-peer access control is enforced by iptables on the WireGuard server;
# this rule only allows traffic that has already passed those checks.
resource "google_compute_firewall" "gke_wireguard_to_nodes" {
  name     = "gke-wireguard-to-nodes-${var.environment}"
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

  source_ranges = [var.wireguard_cidr]
  target_tags   = ["gke-${var.environment}"]
}

# GCP load balancer health check probes (required for external and internal LBs)
resource "google_compute_firewall" "gke_lb_health_checks" {
  name     = "gke-lb-health-checks-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
  }

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = ["gke-${var.environment}"]
}

# Public ingress-nginx-external LoadBalancer traffic (web only). Before GKE
# 1.35.1-gke.1473000, GKE's auto-created k8s-fw-* allow rule for the LB ties in
# priority with deny_ingress (both 1000) and GCP breaks the tie in favor of deny,
# so the LB is unreachable until this lower-priority allow exists. From that
# version GKE's rule is 999 and wins on its own, taking its sources from the
# Service's loadBalancerSourceRanges (0.0.0.0/0 when unset); this rule then adds
# nothing, so it must never be wider than those ranges.
# https://cloud.google.com/kubernetes-engine/docs/concepts/firewall-rules
# Opt-in per environment via enable_public_ingress_firewall.
resource "google_compute_firewall" "gke_public_ingress" {
  count = var.enable_public_ingress_firewall ? 1 : 0

  name     = "gke-public-ingress-${var.environment}"
  network  = var.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = var.public_ingress_source_ranges
  target_tags   = ["gke-${var.environment}"]
}
