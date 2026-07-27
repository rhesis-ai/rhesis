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
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
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

# No credentials: only used for the public, unauthenticated cloudflare_ip_ranges
# data source (modules/kubernetes/gcp), not for managing Cloudflare resources.
provider "cloudflare" {}

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

  # prd uses a private endpoint via the WireGuard server's Shared VPC NIC in the prd nodes subnet.
  # The NIC IP (10.6.1.10) is the MASQUERADE'd source for kubectl → GKE master traffic.
  # Explicitly set to guard against a future module-default change accidentally making prd public.
  enable_private_endpoint = true
  extra_authorized_cidrs  = ["${local.cidrs.prd.wireguard_nic_ip}/32"]

  # polyphemus (test-polyphemus.rhesis.ai) is served via ingress-nginx-external,
  # proxied through Cloudflare — restrict to Cloudflare's live edge IP ranges.
  enable_public_ingress_firewall = true
  use_cloudflare_source_ranges   = true

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

module "arc_gha_prd" {
  source = "../../modules/arc-gha/gcp"

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

# ArgoCD bootstrap is done locally via VPN after GKE is up.

# ── Shared VPC: prd project is the host, rhesis-platform-admin is a service project ──────────
# This allows the WireGuard server (in rhesis-platform-admin) to attach a NIC directly into
# the prd nodes subnet, bypassing GCP's non-transitive peering limitation. Same pattern as dev
# previously used; rhesis-platform-admin can only be a service project of ONE host at a time,
# so dev's Shared VPC host relationship must be removed before applying this.
#
# Subnet user grants are required for:
#   - terraform-wireguard SA: creates the VM NIC during terraform apply
#   - rhesis-platform-admin default compute SA: runtime access by the VM itself

data "google_project" "platform_admin" {
  project_id = "rhesis-platform-admin"
}

resource "google_compute_shared_vpc_host_project" "prd" {
  project = var.project_id
}

resource "google_compute_shared_vpc_service_project" "platform_admin" {
  host_project    = var.project_id
  service_project = "rhesis-platform-admin"
  depends_on      = [google_compute_shared_vpc_host_project.prd]
}

resource "google_compute_subnetwork_iam_member" "wireguard_tf_sa_subnet_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = module.prd.subnet_self_links["nodes"]
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com"
  depends_on = [google_compute_shared_vpc_host_project.prd]
}

resource "google_compute_subnetwork_iam_member" "wireguard_compute_sa_subnet_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = module.prd.subnet_self_links["nodes"]
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:${data.google_project.platform_admin.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_compute_shared_vpc_host_project.prd]
}

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

# ── Return-side peering: prd VPC → wireguard VPC (cross-project) ────
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
