output "vpc_id" {
  description = "The ID of the VPC"
  value       = google_compute_network.vpc.id
}

output "vpc_name" {
  description = "The name of the VPC"
  value       = google_compute_network.vpc.name
}

output "vpc_self_link" {
  description = "The self link of the VPC"
  value       = google_compute_network.vpc.self_link
}

output "subnet_ids" {
  description = "Map of subnet names to their IDs"
  value = var.create_gke_subnets ? {
    nodes  = google_compute_subnetwork.nodes[0].id
    ilb    = google_compute_subnetwork.ilb[0].id
    master = google_compute_subnetwork.master[0].id
    } : {
    main = google_compute_subnetwork.wireguard[0].id
  }
}

output "subnet_self_links" {
  description = "Map of subnet names to their self links"
  value = var.create_gke_subnets ? {
    nodes  = google_compute_subnetwork.nodes[0].self_link
    ilb    = google_compute_subnetwork.ilb[0].self_link
    master = google_compute_subnetwork.master[0].self_link
    } : {
    main = google_compute_subnetwork.wireguard[0].self_link
  }
}

output "secondary_ranges" {
  description = "Secondary IP ranges for pods and services (GKE)"
  value = var.create_gke_subnets ? {
    pods     = var.pod_cidr
    services = var.service_cidr
  } : {}
}
