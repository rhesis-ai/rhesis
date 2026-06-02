# Standalone prd network (no peering). For full deploy with peerings run from infrastructure/

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
    prefix = "terraform/infrastructure/envs/prd"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

module "prd" {
  source = "../../modules/network/gcp"

  project_id         = var.project_id
  environment        = "prd"
  region             = var.region
  network_cidr       = local.cidrs.prd.network
  create_gke_subnets = true
  node_cidr          = local.cidrs.prd.nodes
  ilb_cidr           = local.cidrs.prd.ilb
  master_cidr        = local.cidrs.prd.master
  pod_cidr           = local.cidrs.prd.pods
  service_cidr       = local.cidrs.prd.services
}

module "gke_prd" {
  source = "../../modules/kubernetes/gcp"

  project_id             = var.project_id
  environment            = "prd"
  region                 = var.region
  vpc_name               = module.prd.vpc_name
  nodes_subnet_self_link = module.prd.subnet_self_links["nodes"]
  master_cidr            = local.cidrs.prd.master
  node_cidr              = local.cidrs.prd.nodes
  pod_cidr               = local.cidrs.prd.pods
  service_cidr           = local.cidrs.prd.services
  wireguard_cidr         = local.cidrs.wireguard.network
  machine_type           = "e2-standard-4"
  min_node_count         = 2
  max_node_count         = 5
  deletion_protection    = var.gke_deletion_protection

  # Private endpoint — kubectl access via IAP bastion in the nodes subnet.

  depends_on = [module.prd]
}

module "eso_prd" {
  source = "../../modules/external-secrets/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.gke_prd]
}

module "external_dns_prd" {
  source = "../../modules/external-dns/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

module "internal_dns_prd" {
  source = "../../modules/internal-dns/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

module "ingress_prd" {
  source = "../../modules/ingress/gcp"

  project_id           = var.project_id
  environment          = "prd"
  region               = var.region
  ilb_subnet_self_link = module.prd.subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.prd.ingress_internal_ip

  depends_on = [module.prd]
}

# ── GCS: file storage + CNPG backups ────────────────────────────────
# Previously delegated to the root main.tf, but the root uses a single provider/project
# which conflicts with the multi-project layout. Managed here instead.

module "gcs_prd" {
  source = "../../modules/storage-buckets/gcp"

  project_id  = var.project_id
  environment = "prd"
  location    = var.region

  file_storage_bucket_name = var.file_storage_bucket_name
  cnpg_backup_bucket_name  = var.cnpg_backup_bucket_name
  force_destroy            = var.force_destroy
  file_storage_iam_members = []
  cnpg_backup_iam_members  = []
}

# CloudNativePG Barman: GSA + Workload Identity binding for WAL/base backups.
# Secret IDs must match kubernetes/clusters/prd/rhesis/cnpg-gcs-externalsecret.yaml
module "cnpg_barman_prd" {
  source = "../../modules/cnpg-barman-sa-gcp"

  project_id                 = var.project_id
  environment                = "prd"
  backup_bucket_name         = var.cnpg_backup_bucket_name
  kubernetes_service_account = "rhesis-prd"

  depends_on = [module.gcs_prd, module.gke_prd]
}

# ArgoCD bootstrap is done locally via VPN after GKE is up (requires private endpoint access).

# Allow DNS (port 53) from GKE nodes/pods to the WireGuard server's BIND9 resolver.
# Managed here (not in the wireguard module) because TF_SA_WIREGUARD lacks firewall
# permissions in this project — TF_SA_PRD already has them.
resource "google_compute_firewall" "wireguard_dns" {
  name     = "wireguard-allow-dns-prd"
  network  = module.prd.vpc_name
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

  source_ranges = [local.cidrs.prd.nodes, local.cidrs.prd.pods]
  target_tags   = ["wireguard-server"]

  depends_on = [module.prd]
}

module "bastion_prd" {
  source = "../../modules/bastion/gcp"

  project_id             = var.project_id
  environment            = "prd"
  region                 = var.region
  zone                   = "${var.region}-a"
  nodes_subnet_self_link = module.prd.subnet_self_links["nodes"]
  vpc_name               = module.prd.vpc_name
  iap_members            = var.bastion_iap_members

  depends_on = [module.prd]
}

# ── Return-side peering: prd VPC → wireguard VPC (cross-project) ────
# Kept for BIND9/DNS routing and VPN user → prd internal services (e.g. app.rhesis.ai).
# kubectl no longer routes this way — that now uses IAP bastion + private endpoint.
# Both sides must exist for peering to be ACTIVE.
resource "google_compute_network_peering" "prd_to_wireguard" {
  name         = "peering-prd-to-wireguard"
  network      = module.prd.vpc_self_link
  peer_network = "https://www.googleapis.com/compute/v1/projects/rhesis-platform-admin/global/networks/vpc-wireguard"

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [module.prd]
}

# Generate cluster.env for ingress-nginx-internal (single source of truth)
resource "local_file" "cluster_env_prd" {
  content              = <<-EOT
# Generated by Terraform from terraform/infrastructure/envs/prd. Do not edit by hand.
region=${var.region}
ilb-subnet-name=${module.prd.ilb_subnet_name}
internal-lb-ip=${local.cidrs.prd.ingress_internal_ip}
EOT
  filename             = "${path.module}/../../../../kubernetes/clusters/prd/ingress-nginx-internal/cluster.env"
  file_permission      = "0644"
  directory_permission = "0755"
}
