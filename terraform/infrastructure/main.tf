# Creates all four VPCs and peerings (WireGuard <-> dev, stg, prd).
# Run: terraform init -backend-config="bucket=YOUR_BUCKET_NAME" && terraform apply from infrastructure/

terraform {
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
  node_cidr          = "10.2.0.0/23"
  ilb_cidr           = "10.2.2.0/23"
  master_cidr        = "10.2.4.0/28"
  pod_cidr           = "10.3.0.0/17"
  service_cidr       = "10.3.128.0/17"
}

# stg VPC
module "stg" {
  source = "./modules/network/gcp"

  project_id         = var.project_id
  environment        = "stg"
  region             = var.region
  network_cidr       = "10.4.0.0/15"
  create_gke_subnets = true
  node_cidr          = "10.4.0.0/23"
  ilb_cidr           = "10.4.2.0/23"
  master_cidr        = "10.4.4.0/28"
  pod_cidr           = "10.5.0.0/17"
  service_cidr       = "10.5.128.0/17"
}

# prd VPC
module "prd" {
  source = "./modules/network/gcp"

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

# VPC Peering: WireGuard <-> Dev (bidirectional)
# GCP peering can take 5-15+ minutes; default 4m often times out.
resource "google_compute_network_peering" "wireguard_to_dev" {
  name         = "peering-wireguard-to-dev"
  network      = module.wireguard.vpc_self_link
  peer_network = module.dev.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts {
    create = "15m"
  }
}

resource "google_compute_network_peering" "dev_to_wireguard" {
  name         = "peering-dev-to-wireguard"
  network      = module.dev.vpc_self_link
  peer_network = module.wireguard.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts {
    create = "15m"
  }
}

# VPC Peering: WireGuard <-> stg (bidirectional)
resource "google_compute_network_peering" "wireguard_to_stg" {
  name         = "peering-wireguard-to-stg"
  network      = module.wireguard.vpc_self_link
  peer_network = module.stg.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts {
    create = "15m"
  }
}

resource "google_compute_network_peering" "stg_to_wireguard" {
  name         = "peering-stg-to-wireguard"
  network      = module.stg.vpc_self_link
  peer_network = module.wireguard.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts {
    create = "15m"
  }
}

# VPC Peering: WireGuard <-> prd (bidirectional)
resource "google_compute_network_peering" "wireguard_to_prd" {
  name         = "peering-wireguard-to-prd"
  network      = module.wireguard.vpc_self_link
  peer_network = module.prd.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts {
    create = "15m"
  }
}

resource "google_compute_network_peering" "prd_to_wireguard" {
  name         = "peering-prd-to-wireguard"
  network      = module.prd.vpc_self_link
  peer_network = module.wireguard.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts {
    create = "15m"
  }
}

# GKE private clusters (dev, stg, prd)
module "gke_dev" {
  source = "./modules/kubernetes/gcp"

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

module "gke_stg" {
  source = "./modules/kubernetes/gcp"

  project_id             = var.project_id
  environment            = "stg"
  region                 = var.region
  vpc_name               = module.stg.vpc_name
  nodes_subnet_self_link = module.stg.subnet_self_links["nodes"]
  master_cidr            = "10.4.4.0/28"
  node_cidr              = "10.4.0.0/23"
  pod_cidr               = "10.5.0.0/17"
  service_cidr           = "10.5.128.0/17"
  wireguard_cidr         = var.wireguard_cidr
  machine_type           = "e2-standard-2"
  min_node_count         = 1
  max_node_count         = 3
  deletion_protection    = false

  depends_on = [module.stg]
}

module "gke_prd" {
  source = "./modules/kubernetes/gcp"

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

# WireGuard VPN server
module "wireguard_server" {
  source = "./modules/wireguard/gcp"

  project_id          = var.project_id
  region              = var.region
  vpc_name            = module.wireguard.vpc_name
  subnet_self_link    = module.wireguard.subnet_self_links["main"]
  deletion_protection = var.wireguard_deletion_protection

  wireguard_peers = var.wireguard_peers

  subnet_cidrs = {
    dev = "10.2.0.0/15"
    stg = "10.4.0.0/15"
    prd = "10.6.0.0/15"
  }

  master_cidrs = {
    dev = "10.2.4.0/28"
    stg = "10.4.4.0/28"
    prd = "10.6.4.0/28"
  }

  ssh_keys = var.ssh_keys

  depends_on = [
    module.wireguard,
    google_compute_network_peering.wireguard_to_dev,
    google_compute_network_peering.wireguard_to_stg,
    google_compute_network_peering.wireguard_to_prd
  ]
}
