# Creates VPCs and peerings for enabled environments only.
# Run: terraform init -backend-config=backend.conf && terraform apply
#
# Dev-only:  terraform apply -var='enabled_environments=["dev"]'
# All envs:  terraform apply  (default: dev, stg, prd)

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    prefix = "terraform/infrastructure/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  env_enabled = { for env in var.enabled_environments : env => true }
  dev_enabled = lookup(local.env_enabled, "dev", false)
  stg_enabled = lookup(local.env_enabled, "stg", false)
  prd_enabled = lookup(local.env_enabled, "prd", false)
}

# ── VPCs ──────────────────────────────────────────────────────────────

module "wireguard" {
  source = "./modules/network/gcp"

  project_id         = var.project_id
  environment        = "wireguard"
  region             = var.region
  network_cidr       = local.cidrs.wireguard.network
  create_gke_subnets = false
}

module "dev" {
  source = "./modules/network/gcp"
  count  = local.dev_enabled ? 1 : 0

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

module "stg" {
  source = "./modules/network/gcp"
  count  = local.stg_enabled ? 1 : 0

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

module "prd" {
  source = "./modules/network/gcp"
  count  = local.prd_enabled ? 1 : 0

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

# ── VPC Peering: WireGuard <-> envs ──────────────────────────────────
# GCP peering can take 5-15+ minutes; default 4m often times out.

resource "google_compute_network_peering" "wireguard_to_dev" {
  count = local.dev_enabled ? 1 : 0

  name         = "peering-wireguard-to-dev"
  network      = module.wireguard.vpc_self_link
  peer_network = module.dev[0].vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }
}

resource "google_compute_network_peering" "dev_to_wireguard" {
  count = local.dev_enabled ? 1 : 0

  name         = "peering-dev-to-wireguard"
  network      = module.dev[0].vpc_self_link
  peer_network = module.wireguard.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [google_compute_network_peering.wireguard_to_dev]
}

resource "google_compute_network_peering" "wireguard_to_stg" {
  count = local.stg_enabled ? 1 : 0

  name         = "peering-wireguard-to-stg"
  network      = module.wireguard.vpc_self_link
  peer_network = module.stg[0].vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }
}

resource "google_compute_network_peering" "stg_to_wireguard" {
  count = local.stg_enabled ? 1 : 0

  name         = "peering-stg-to-wireguard"
  network      = module.stg[0].vpc_self_link
  peer_network = module.wireguard.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [google_compute_network_peering.wireguard_to_stg]
}

resource "google_compute_network_peering" "wireguard_to_prd" {
  count = local.prd_enabled ? 1 : 0

  name         = "peering-wireguard-to-prd"
  network      = module.wireguard.vpc_self_link
  peer_network = module.prd[0].vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }
}

resource "google_compute_network_peering" "prd_to_wireguard" {
  count = local.prd_enabled ? 1 : 0

  name         = "peering-prd-to-wireguard"
  network      = module.prd[0].vpc_self_link
  peer_network = module.wireguard.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [google_compute_network_peering.wireguard_to_prd]
}

# ── GKE private clusters ─────────────────────────────────────────────

module "gke_dev" {
  source = "./modules/kubernetes/gcp"
  count  = local.dev_enabled ? 1 : 0

  project_id             = var.project_id
  environment            = "dev"
  region                 = var.region
  vpc_name               = module.dev[0].vpc_name
  nodes_subnet_self_link = module.dev[0].subnet_self_links["nodes"]
  master_cidr            = local.cidrs.dev.master
  node_cidr              = local.cidrs.dev.nodes
  pod_cidr               = local.cidrs.dev.pods
  service_cidr           = local.cidrs.dev.services
  wireguard_cidr         = local.cidrs.wireguard.network
  extra_authorized_cidrs = ["10.2.1.200/32"]
  machine_type           = "e2-medium"
  min_node_count         = 1
  max_node_count         = 2
  deletion_protection    = false

  depends_on = [module.dev]
}

module "gke_stg" {
  source = "./modules/kubernetes/gcp"
  count  = local.stg_enabled ? 1 : 0

  project_id             = var.project_id
  environment            = "stg"
  region                 = var.region
  vpc_name               = module.stg[0].vpc_name
  nodes_subnet_self_link = module.stg[0].subnet_self_links["nodes"]
  master_cidr            = local.cidrs.stg.master
  node_cidr              = local.cidrs.stg.nodes
  pod_cidr               = local.cidrs.stg.pods
  service_cidr           = local.cidrs.stg.services
  wireguard_cidr         = local.cidrs.wireguard.network
  extra_authorized_cidrs = ["10.4.1.200/32"]
  machine_type           = "e2-standard-2"
  min_node_count         = 1
  max_node_count         = 3
  deletion_protection    = false

  depends_on = [module.stg]
}

module "gke_prd" {
  source = "./modules/kubernetes/gcp"
  count  = local.prd_enabled ? 1 : 0

  project_id             = var.project_id
  environment            = "prd"
  region                 = var.region
  vpc_name               = module.prd[0].vpc_name
  nodes_subnet_self_link = module.prd[0].subnet_self_links["nodes"]
  master_cidr            = local.cidrs.prd.master
  node_cidr              = local.cidrs.prd.nodes
  pod_cidr               = local.cidrs.prd.pods
  service_cidr           = local.cidrs.prd.services
  wireguard_cidr         = local.cidrs.wireguard.network
  extra_authorized_cidrs = ["10.6.1.200/32"]
  machine_type           = "e2-standard-4"
  min_node_count         = 2
  max_node_count         = 5
  deletion_protection    = false

  depends_on = [module.prd]
}

# ── External Secrets Operator (ESO) ──────────────────────────────────

module "eso_dev" {
  source = "./modules/external-secrets/gcp"
  count  = local.dev_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.gke_dev]
}

module "eso_stg" {
  source = "./modules/external-secrets/gcp"
  count  = local.stg_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "stg"

  depends_on = [module.gke_stg]
}

module "eso_prd" {
  source = "./modules/external-secrets/gcp"
  count  = local.prd_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.gke_prd]
}

# ── External DNS ─────────────────────────────────────────────────────

module "external_dns_dev" {
  source = "./modules/external-dns/gcp"
  count  = local.dev_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.eso_dev]
}

module "external_dns_stg" {
  source = "./modules/external-dns/gcp"
  count  = local.stg_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "stg"

  depends_on = [module.eso_stg]
}

module "external_dns_prd" {
  source = "./modules/external-dns/gcp"
  count  = local.prd_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

# ── Internal DNS ─────────────────────────────────────────────────────

module "internal_dns_dev" {
  source = "./modules/internal-dns/gcp"
  count  = local.dev_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "dev"

  depends_on = [module.eso_dev]
}

module "internal_dns_stg" {
  source = "./modules/internal-dns/gcp"
  count  = local.stg_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "stg"

  depends_on = [module.eso_stg]
}

module "internal_dns_prd" {
  source = "./modules/internal-dns/gcp"
  count  = local.prd_enabled ? 1 : 0

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

# ── Ingress internal LB static IPs ──────────────────────────────────

module "ingress_dev" {
  source = "./modules/ingress/gcp"
  count  = local.dev_enabled ? 1 : 0

  project_id           = var.project_id
  environment          = "dev"
  region               = var.region
  ilb_subnet_self_link = module.dev[0].subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.dev.ingress_internal_ip

  depends_on = [module.dev]
}

module "ingress_stg" {
  source = "./modules/ingress/gcp"
  count  = local.stg_enabled ? 1 : 0

  project_id           = var.project_id
  environment          = "stg"
  region               = var.region
  ilb_subnet_self_link = module.stg[0].subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.stg.ingress_internal_ip

  depends_on = [module.stg]
}

module "ingress_prd" {
  source = "./modules/ingress/gcp"
  count  = local.prd_enabled ? 1 : 0

  project_id           = var.project_id
  environment          = "prd"
  region               = var.region
  ilb_subnet_self_link = module.prd[0].subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.prd.ingress_internal_ip

  depends_on = [module.prd]
}

# ── WireGuard VPN server ─────────────────────────────────────────────
# Multi-NIC: WireGuard VPC + one NIC per enabled env for kubectl routing.
# GCP allows max 2 vNICs for <=2 vCPUs; 4 vCPUs → 4 vNICs.

module "wireguard_server" {
  source = "./modules/wireguard/gcp"

  project_id          = var.project_id
  region              = var.region
  vpc_name            = module.wireguard.vpc_name
  subnet_self_link    = module.wireguard.subnet_self_links["main"]
  deletion_protection = var.wireguard_deletion_protection

  machine_type = local.stg_enabled || local.prd_enabled ? "e2-standard-4" : "e2-medium"

  wireguard_peers = var.wireguard_peers

  subnet_cidrs = {
    for env, cidr in local.cidrs : env => cidr.network
    if env != "wireguard" && lookup(local.env_enabled, env, false)
  }
  master_cidrs = {
    for env, cidr in local.cidrs : env => cidr.master
    if env != "wireguard" && lookup(local.env_enabled, env, false)
  }

  bind9_tsig_keys = merge(
    local.dev_enabled ? {
      dev = {
        keyname = module.internal_dns_dev[0].tsig_keyname
        secret  = module.internal_dns_dev[0].tsig_secret
      }
    } : {},
    local.stg_enabled ? {
      stg = {
        keyname = module.internal_dns_stg[0].tsig_keyname
        secret  = module.internal_dns_stg[0].tsig_secret
      }
    } : {},
    local.prd_enabled ? {
      prd = {
        keyname = module.internal_dns_prd[0].tsig_keyname
        secret  = module.internal_dns_prd[0].tsig_secret
      }
    } : {}
  )

  env_nics = concat(
    local.dev_enabled ? [{
      subnet_self_link = module.dev[0].subnet_self_links["nodes"]
      network_ip       = "10.2.1.200"
      master_cidr      = local.cidrs.dev.master
      environment      = "dev"
      pod_cidr         = local.cidrs.dev.pods
      service_cidr     = local.cidrs.dev.services
      node_cidr        = local.cidrs.dev.nodes
      vpc_name         = module.dev[0].vpc_name
    }] : [],
    local.stg_enabled ? [{
      subnet_self_link = module.stg[0].subnet_self_links["nodes"]
      network_ip       = "10.4.1.200"
      master_cidr      = local.cidrs.stg.master
      environment      = "stg"
      pod_cidr         = local.cidrs.stg.pods
      service_cidr     = local.cidrs.stg.services
      node_cidr        = local.cidrs.stg.nodes
      vpc_name         = module.stg[0].vpc_name
    }] : [],
    local.prd_enabled ? [{
      subnet_self_link = module.prd[0].subnet_self_links["nodes"]
      network_ip       = "10.6.1.200"
      master_cidr      = local.cidrs.prd.master
      environment      = "prd"
      pod_cidr         = local.cidrs.prd.pods
      service_cidr     = local.cidrs.prd.services
      node_cidr        = local.cidrs.prd.nodes
      vpc_name         = module.prd[0].vpc_name
    }] : []
  )

  depends_on = [
    module.wireguard,
    google_compute_network_peering.wireguard_to_dev,
    google_compute_network_peering.wireguard_to_stg,
    google_compute_network_peering.wireguard_to_prd,
    module.internal_dns_dev,
    module.internal_dns_stg,
    module.internal_dns_prd
  ]
}

# ── ArgoCD Bootstrap ─────────────────────────────────────────────────
# Automates: kubectl create ns argocd → kustomize install → root app.
# Must run from VPN since GKE clusters are private.

module "argocd_dev" {
  source = "./modules/argocd"
  count  = local.dev_enabled ? 1 : 0

  project_id   = var.project_id
  region       = var.region
  cluster_name = module.gke_dev[0].cluster_name
  environment  = "dev"
  repo_root    = abspath("${path.module}/../..")

  depends_on = [
    module.gke_dev,
    module.wireguard_server
  ]
}

module "argocd_stg" {
  source = "./modules/argocd"
  count  = local.stg_enabled ? 1 : 0

  project_id   = var.project_id
  region       = var.region
  cluster_name = module.gke_stg[0].cluster_name
  environment  = "stg"
  repo_root    = abspath("${path.module}/../..")

  depends_on = [
    module.gke_stg,
    module.wireguard_server
  ]
}

module "argocd_prd" {
  source = "./modules/argocd"
  count  = local.prd_enabled ? 1 : 0

  project_id   = var.project_id
  region       = var.region
  cluster_name = module.gke_prd[0].cluster_name
  environment  = "prd"
  repo_root    = abspath("${path.module}/../..")

  depends_on = [
    module.gke_prd,
    module.wireguard_server
  ]
}
