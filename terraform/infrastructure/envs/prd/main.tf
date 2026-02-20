# Standalone prd network (no peering). For full deploy with peerings run from infrastructure/

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
  deletion_protection    = true

  depends_on = [module.prd]
}
