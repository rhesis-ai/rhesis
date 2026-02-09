# Standalone stg network (no peering). For full deploy with peerings run from infrastructure/

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

module "stg" {
  source = "../../modules/network/gcp"

  project_id         = var.project_id
  environment        = "stg"
  region             = var.region
  network_cidr       = "10.4.0.0/15"
  create_gke_subnets = true
  node_cidr         = "10.4.0.0/23"
  ilb_cidr          = "10.4.2.0/23"
  master_cidr       = "10.4.4.0/28"
  pod_cidr          = "10.5.0.0/17"
  service_cidr      = "10.5.128.0/17"
}
