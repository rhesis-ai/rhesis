# Creates all four VPCs and peerings (WireGuard <-> dev, staging, prod).
# Run: terraform init && terraform apply from infrastructure/

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "local" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# WireGuard VPC
module "wireguard" {
  source = "./modules/network/gcp"

  project_id         = var.project_id
  environment        = "wireguard"
  region             = var.region
  network_cidr       = var.wireguard_cidr
  create_gke_subnets = false
}

# Dev VPC
module "dev" {
  source = "./modules/network/gcp"

  project_id         = var.project_id
  environment        = "dev"
  region             = var.region
  network_cidr       = "10.2.0.0/15"
  create_gke_subnets = true
  node_cidr         = "10.2.0.0/23"
  ilb_cidr          = "10.2.2.0/23"
  master_cidr       = "10.2.4.0/28"
  pod_cidr          = "10.3.0.0/17"
  service_cidr      = "10.3.128.0/17"
}

# Staging VPC
module "staging" {
  source = "./modules/network/gcp"

  project_id         = var.project_id
  environment        = "staging"
  region             = var.region
  network_cidr       = "10.4.0.0/15"
  create_gke_subnets = true
  node_cidr         = "10.4.0.0/23"
  ilb_cidr          = "10.4.2.0/23"
  master_cidr       = "10.4.4.0/28"
  pod_cidr          = "10.5.0.0/17"
  service_cidr      = "10.5.128.0/17"
}

# Prod VPC
module "prod" {
  source = "./modules/network/gcp"

  project_id         = var.project_id
  environment        = "prod"
  region             = var.region
  network_cidr       = "10.6.0.0/15"
  create_gke_subnets = true
  node_cidr         = "10.6.0.0/23"
  ilb_cidr          = "10.6.2.0/23"
  master_cidr       = "10.6.4.0/28"
  pod_cidr          = "10.7.0.0/17"
  service_cidr      = "10.7.128.0/17"
}

# VPC Peering: WireGuard <-> Dev (bidirectional)
resource "google_compute_network_peering" "wireguard_to_dev" {
  name         = "peering-wireguard-to-dev"
  network      = module.wireguard.vpc_self_link
  peer_network = module.dev.vpc_self_link
}

resource "google_compute_network_peering" "dev_to_wireguard" {
  name         = "peering-dev-to-wireguard"
  network      = module.dev.vpc_self_link
  peer_network = module.wireguard.vpc_self_link
}

# VPC Peering: WireGuard <-> Staging (bidirectional)
resource "google_compute_network_peering" "wireguard_to_staging" {
  name         = "peering-wireguard-to-staging"
  network      = module.wireguard.vpc_self_link
  peer_network = module.staging.vpc_self_link
}

resource "google_compute_network_peering" "staging_to_wireguard" {
  name         = "peering-staging-to-wireguard"
  network      = module.staging.vpc_self_link
  peer_network = module.wireguard.vpc_self_link
}

# VPC Peering: WireGuard <-> Prod (bidirectional)
resource "google_compute_network_peering" "wireguard_to_prod" {
  name         = "peering-wireguard-to-prod"
  network      = module.wireguard.vpc_self_link
  peer_network = module.prod.vpc_self_link
}

resource "google_compute_network_peering" "prod_to_wireguard" {
  name         = "peering-prod-to-wireguard"
  network      = module.prod.vpc_self_link
  peer_network = module.wireguard.vpc_self_link
}
