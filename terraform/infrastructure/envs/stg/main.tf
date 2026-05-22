# Standalone stg network (no peering). For full deploy with peerings run from infrastructure/

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
  backend "gcs" {
    prefix = "terraform/infrastructure/envs/stg"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "stg" {
  source = "../../modules/network/gcp"

  project_id         = var.project_id
  environment        = "stg"
  region             = var.region
  network_cidr       = local.cidrs.stg.network
  create_gke_subnets = true
  node_cidr          = local.cidrs.stg.nodes
  ilb_cidr           = local.cidrs.stg.ilb
  master_cidr        = local.cidrs.stg.master
  pod_cidr           = local.cidrs.stg.pods
  service_cidr       = local.cidrs.stg.services
}

module "gke_stg" {
  source = "../../modules/kubernetes/gcp"

  project_id             = var.project_id
  environment            = "stg"
  region                 = var.region
  vpc_name               = module.stg.vpc_name
  nodes_subnet_self_link = module.stg.subnet_self_links["nodes"]
  master_cidr            = local.cidrs.stg.master
  node_cidr              = local.cidrs.stg.nodes
  pod_cidr               = local.cidrs.stg.pods
  service_cidr           = local.cidrs.stg.services
  wireguard_cidr         = local.cidrs.wireguard.network
  machine_type           = "e2-standard-2"
  min_node_count         = 1
  max_node_count         = 3
  deletion_protection    = var.gke_deletion_protection

  depends_on = [module.stg]
}

module "eso_stg" {
  source = "../../modules/external-secrets/gcp"

  project_id  = var.project_id
  environment = "stg"

  depends_on = [module.gke_stg]
}

module "external_dns_stg" {
  source = "../../modules/external-dns/gcp"

  project_id  = var.project_id
  environment = "stg"

  depends_on = [module.eso_stg]
}

module "internal_dns_stg" {
  source = "../../modules/internal-dns/gcp"

  project_id  = var.project_id
  environment = "stg"

  depends_on = [module.eso_stg]
}

module "ingress_stg" {
  source = "../../modules/ingress/gcp"

  project_id           = var.project_id
  environment          = "stg"
  region               = var.region
  ilb_subnet_self_link = module.stg.subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.stg.ingress_internal_ip

  depends_on = [module.stg]
}

# GCS buckets: managed by terraform/infrastructure (root) — not duplicated here.
# ArgoCD bootstrap is done locally via VPN after GKE is up (requires private endpoint access).

# ── Shared VPC: stg project is the host, rhesis-platform-admin is a service project ──────────
# This allows the WireGuard server (in rhesis-platform-admin) to attach a second NIC
# directly into the stg nodes subnet, bypassing GCP's non-transitive peering limitation
# that would otherwise block WireGuard VPC → stg VPC → GKE master (3-hop peering).
#
# Subnet user grants are required for:
#   - terraform-wireguard SA: creates the VM NIC during terraform apply
#   - rhesis-platform-admin default compute SA: runtime access by the VM itself

resource "google_compute_shared_vpc_host_project" "stg" {
  project = var.project_id
}

resource "google_compute_subnetwork_iam_member" "wireguard_tf_sa_subnet_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = module.stg.subnet_self_links["nodes"]
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com"
  depends_on = [google_compute_shared_vpc_host_project.stg]
}

resource "google_compute_subnetwork_iam_member" "wireguard_compute_sa_subnet_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = module.stg.subnet_self_links["nodes"]
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:211583725977-compute@developer.gserviceaccount.com"
  depends_on = [google_compute_shared_vpc_host_project.stg]
}

# Allow DNS (port 53) from GKE nodes/pods to the WireGuard server's BIND9 resolver.
# Managed here (not in the wireguard module) because TF_SA_WIREGUARD lacks firewall
# permissions in this project — TF_SA_STG already has them.
resource "google_compute_firewall" "wireguard_dns" {
  name     = "wireguard-allow-dns-stg"
  network  = module.stg.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["53"]
  }
  allow {
    protocol = "udp"
    ports    = ["53"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [local.cidrs.stg.nodes, local.cidrs.stg.pods]
  target_tags   = ["wireguard-server"]

  depends_on = [module.stg]
}

# ── Return-side peering: stg VPC → wireguard VPC (cross-project) ────
resource "google_compute_network_peering" "stg_to_wireguard" {
  name         = "peering-stg-to-wireguard"
  network      = module.stg.vpc_self_link
  peer_network = "https://www.googleapis.com/compute/v1/projects/rhesis-platform-admin/global/networks/vpc-wireguard"

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [module.stg]
}

# Generate cluster.env for ingress-nginx-internal (single source of truth)
resource "local_file" "cluster_env_stg" {
  content              = <<-EOT
# Generated by Terraform from terraform/infrastructure/envs/stg. Do not edit by hand.
region=${var.region}
ilb-subnet-name=${module.stg.ilb_subnet_name}
internal-lb-ip=${local.cidrs.stg.ingress_internal_ip}
EOT
  filename             = "${path.module}/../../../../kubernetes/clusters/stg/ingress-nginx-internal/cluster.env"
  file_permission      = "0644"
  directory_permission = "0755"
}
