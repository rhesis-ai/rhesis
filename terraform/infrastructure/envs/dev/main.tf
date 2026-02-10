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
  node_cidr         = "10.2.0.0/23"
  ilb_cidr          = "10.2.2.0/23"
  master_cidr       = "10.2.4.0/28"
  pod_cidr          = "10.3.0.0/17"
  service_cidr      = "10.3.128.0/17"
}
