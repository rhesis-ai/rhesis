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
  network_cidr       = "10.6.0.0/15"
  create_gke_subnets = true
  node_cidr          = "10.6.0.0/23"
  ilb_cidr           = "10.6.2.0/23"
  master_cidr        = "10.6.4.0/28"
  pod_cidr           = "10.7.0.0/17"
  service_cidr       = "10.7.128.0/17"
}

module "gke_prd" {
  source = "../../modules/kubernetes/gcp"

  project_id             = var.project_id
  environment            = "prd"
  region                 = var.region
  vpc_name               = module.prd.vpc_name
  nodes_subnet_self_link = module.prd.subnet_self_links["nodes"]
  master_cidr            = "10.6.4.0/28"
  node_cidr              = "10.6.0.0/23"
  pod_cidr               = "10.7.0.0/17"
  service_cidr           = "10.7.128.0/17"
  wireguard_cidr         = var.wireguard_cidr
  machine_type           = "e2-standard-4"
  min_node_count         = 2
  max_node_count         = 5
  deletion_protection    = true

  depends_on = [module.prd]
}
