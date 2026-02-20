# Standalone Dev network (no peering). For full deploy with peerings run from infrastructure/

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
  machine_type           = "e2-medium"
  min_node_count         = 1
  max_node_count         = 2
  deletion_protection    = false

  depends_on = [module.dev]
}
