resource "google_container_cluster" "cluster" {
  name     = "gke-${var.environment}"
  location = var.region
  project  = var.project_id

  network    = var.vpc_name
  subnetwork = var.nodes_subnet_self_link

  remove_default_node_pool = true
  initial_node_count       = 1

  private_cluster_config {
    enable_private_endpoint = var.enable_private_endpoint
    enable_private_nodes    = true
    master_ipv4_cidr_block  = var.master_cidr
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.wireguard_cidr
      display_name = "wireguard-vpn"
    }
    # WireGuard server env NIC IPs: traffic forwarded by the WireGuard server
    # to the GKE master is MASQUERADE'd to these IPs (one NIC per env VPC)
    dynamic "cidr_blocks" {
      for_each = var.extra_authorized_cidrs
      content {
        cidr_block   = cidr_blocks.value
        display_name = "wireguard-server-env-nic"
      }
    }
    gcp_public_cidrs_access_enabled = false
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

  # Declared so these stop being invisible drift: they were trimmed with gcloud during the
  # 2026-08 cost work and nothing in Terraform owned them, meaning any future change here
  # would silently re-enable paid metric collection. Defaults match what all three clusters
  # already run, so adding this is a no-op on apply.
  monitoring_config {
    enable_components = var.monitoring_enable_components
    managed_prometheus {
      enabled = var.enable_managed_prometheus
    }
  }

  logging_config {
    enable_components = var.logging_enable_components
  }

  deletion_protection = var.deletion_protection
}
