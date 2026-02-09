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
  network_cidr       = "10.2.0.0/15"
  create_gke_subnets = true
  node_cidr          = "10.2.0.0/23"
  ilb_cidr           = "10.2.2.0/23"
  master_cidr        = "10.2.4.0/28"
  pod_cidr           = "10.3.0.0/17"
  service_cidr       = "10.3.128.0/17"
}

module "gke_dev" {
  source = "../../modules/kubernetes/gcp"

  project_id             = var.project_id
  environment            = "dev"
  region                 = var.region
  vpc_name               = module.dev.vpc_name
  nodes_subnet_self_link = module.dev.subnet_self_links["nodes"]
  master_cidr            = "10.2.4.0/28"
  node_cidr              = "10.2.0.0/23"
  pod_cidr               = "10.3.0.0/17"
  service_cidr           = "10.3.128.0/17"
  wireguard_cidr         = var.wireguard_cidr
  machine_type           = "e2-medium"
  min_node_count         = 1
  max_node_count         = 2
  deletion_protection    = false

  depends_on = [module.dev]
}
