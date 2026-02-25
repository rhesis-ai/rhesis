# Standalone stg network (no peering). For full deploy with peerings run from infrastructure/

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
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
  deletion_protection    = false

  depends_on = [module.stg]
}
