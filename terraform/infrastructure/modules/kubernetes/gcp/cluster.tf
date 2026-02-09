resource "google_container_cluster" "cluster" {
  name     = "gke-${var.environment}"
  location = var.region
  project  = var.project_id

  network    = var.vpc_name
  subnetwork = var.nodes_subnet_self_link

  remove_default_node_pool = true
  initial_node_count       = 1

  private_cluster_config {
    enable_private_endpoint = true
    enable_private_nodes    = true
    master_ipv4_cidr_block  = var.master_cidr
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.wireguard_cidr
      display_name = "wireguard-vpn"
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pod_range_name
    services_secondary_range_name = var.service_range_name
  }

  release_channel {
    channel = var.release_channel
  }

  deletion_protection = var.deletion_protection
}
