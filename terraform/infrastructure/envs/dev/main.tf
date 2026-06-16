# Standalone Dev network (no peering). For full deploy with peerings run from infrastructure/

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
    prefix = "terraform/infrastructure/envs/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Read WireGuard server's reserved external IP from its Terraform state.
data "terraform_remote_state" "wireguard" {
  backend = "gcs"
  config = {
    bucket = var.state_bucket
    prefix = "terraform/infrastructure/envs/wireguard"
  }
}

module "dev" {
  source = "../../modules/network/gcp"

  project_id         = var.project_id
  environment        = "dev"
  region             = var.region
  network_cidr       = local.cidrs.dev.network
  create_gke_subnets = true
  node_cidr          = local.cidrs.dev.nodes
  ilb_cidr           = local.cidrs.dev.ilb
  master_cidr        = local.cidrs.dev.master
  pod_cidr           = local.cidrs.dev.pods
  service_cidr       = local.cidrs.dev.services
}

module "gke_dev" {
  source = "../../modules/kubernetes/gcp"

  project_id             = var.project_id
  environment            = "dev"
  region                 = var.region
  vpc_name               = module.dev.vpc_name
  nodes_subnet_self_link = module.dev.subnet_self_links["nodes"]
  master_cidr            = local.cidrs.dev.master
  node_cidr              = local.cidrs.dev.nodes
  pod_cidr               = local.cidrs.dev.pods
  service_cidr           = local.cidrs.dev.services
  wireguard_cidr         = local.cidrs.wireguard.network
  # e2-medium (~940m allocatable CPU/node) cannot fit the rhesis stack (~1400m requests)
  # plus platform DaemonSets; causes OOM, probe timeouts, and failed scale-up.
  # Match stg sizing; keep min 2 nodes so cluster-autoscaler does not pack everything on one VM.
  machine_type           = "e2-standard-2"
  min_node_count         = 2
  max_node_count         = 6
  deletion_protection    = var.gke_deletion_protection

  # dev now uses a public endpoint locked to the WireGuard server's external IP (same pattern as stg).
  enable_private_endpoint = false
  extra_authorized_cidrs  = ["${data.terraform_remote_state.wireguard.outputs.wireguard_public_ip}/32"]

  depends_on = [module.dev]
}

module "eso_dev" {
  source = "../../modules/external-secrets/gcp"

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.gke_dev]
}

module "external_dns_dev" {
  source = "../../modules/external-dns/gcp"

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.eso_dev]
}

module "arc_gha_dev" {
  source = "../../modules/arc-gha/gcp"

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.eso_dev]
}

module "internal_dns_dev" {
  source = "../../modules/internal-dns/gcp"

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.eso_dev]
}

module "ingress_dev" {
  source = "../../modules/ingress/gcp"

  project_id           = var.project_id
  environment          = "dev"
  region               = var.region
  ilb_subnet_self_link = module.dev.subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.dev.ingress_internal_ip

  depends_on = [module.dev]
}

# ── GCS: file storage (no CNPG backup bucket in dev — Bitnami PostgreSQL) ─
# Previously delegated to the root main.tf, but the root uses a single provider/project
# which conflicts with the multi-project layout. Managed here instead.

module "gcs_dev" {
  source = "../../modules/storage-buckets/gcp"

  project_id  = var.project_id
  environment = "dev"
  location    = var.region

  file_storage_bucket_name = var.file_storage_bucket_name
  cnpg_backup_bucket_name  = null
  force_destroy            = var.force_destroy
  file_storage_iam_members = []
  cnpg_backup_iam_members  = []
}

# ArgoCD bootstrap is done locally via VPN after GKE is up.

# Allow DNS (port 53) from GKE nodes/pods to the WireGuard server's BIND9 resolver.
# Managed here (not in the wireguard module) because TF_SA_WIREGUARD lacks firewall
# permissions in this project — TF_SA_DEV already has them.
resource "google_compute_firewall" "wireguard_dns" {
  name     = "wireguard-allow-dns-dev"
  network  = module.dev.vpc_name
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

  source_ranges = [local.cidrs.dev.nodes, local.cidrs.dev.pods]
  target_tags   = ["wireguard-server"]

  depends_on = [module.dev]
}

# ── Return-side peering: dev VPC → wireguard VPC (cross-project) ────
# Required for BIND9/DNS routing from GKE pods and for kubectl via WireGuard VPN.
# Both sides must exist for ACTIVE state.
# wireguard VPC self-link is deterministic: vpc-wireguard in rhesis-platform-admin.
resource "google_compute_network_peering" "dev_to_wireguard" {
  name         = "peering-dev-to-wireguard"
  network      = module.dev.vpc_self_link
  peer_network = "https://www.googleapis.com/compute/v1/projects/rhesis-platform-admin/global/networks/vpc-wireguard"

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [module.dev]
}

# Generate cluster.env for ingress-nginx-internal (single source of truth)
resource "local_file" "cluster_env_dev" {
  content              = <<-EOT
# Generated by Terraform from terraform/infrastructure/envs/dev. Do not edit by hand.
region=${var.region}
ilb-subnet-name=${module.dev.ilb_subnet_name}
internal-lb-ip=${local.cidrs.dev.ingress_internal_ip}
EOT
  filename             = "${path.module}/../../../../kubernetes/clusters/dev/ingress-nginx-internal/cluster.env"
  file_permission      = "0644"
  directory_permission = "0755"
}
