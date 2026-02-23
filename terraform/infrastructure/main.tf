# Creates all four VPCs and peerings (WireGuard <-> dev, stg, prd).
# Run: terraform init -backend-config=backend.conf && terraform apply

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
  network_cidr       = local.cidrs.wireguard.network
  create_gke_subnets = false
}

# Dev VPC
module "dev" {
  source = "./modules/network/gcp"

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

# stg VPC
module "stg" {
  source = "./modules/network/gcp"

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

# prd VPC
module "prd" {
  source = "./modules/network/gcp"

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
  extra_authorized_cidrs = ["10.4.1.200/32"]
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
  master_cidr            = local.cidrs.prd.master
  node_cidr              = local.cidrs.prd.nodes
  pod_cidr               = local.cidrs.prd.pods
  service_cidr           = local.cidrs.prd.services
  wireguard_cidr         = local.cidrs.wireguard.network
  extra_authorized_cidrs = ["10.6.1.200/32"]
  machine_type           = "e2-standard-4"
  min_node_count         = 2
  max_node_count         = 5
  deletion_protection    = true

  depends_on = [module.prd]
}


# WireGuard VPN server (multi-NIC: WireGuard VPC + one NIC per env for kubectl routing)
# GCP allows max 2 vNICs for 2-or-fewer vCPUs; 4 vCPUs → 4 vNICs. So we need e2-standard-4.
module "wireguard_server" {
  source = "./modules/wireguard/gcp"

  project_id          = var.project_id
  region              = var.region
  vpc_name            = module.wireguard.vpc_name
  subnet_self_link    = module.wireguard.subnet_self_links["main"]
  deletion_protection = var.wireguard_deletion_protection
  machine_type        = "e2-standard-4"

  wireguard_peers = var.wireguard_peers

  subnet_cidrs = { for env, cidr in local.cidrs : env => cidr.network if env != "wireguard" }
  master_cidrs = { for env, cidr in local.cidrs : env => cidr.master if env != "wireguard" }

  # Extra NICs in each env VPC so the server can forward kubectl traffic to GKE master
  env_nics = [
    {
      subnet_self_link = module.dev.subnet_self_links["nodes"]
      network_ip       = "10.2.1.200"
      master_cidr      = local.cidrs.dev.master
    },
    {
      subnet_self_link = module.stg.subnet_self_links["nodes"]
      network_ip       = "10.4.1.200"
      master_cidr      = local.cidrs.stg.master
    },
    {
      subnet_self_link = module.prd.subnet_self_links["nodes"]
      network_ip       = "10.6.1.200"
      master_cidr      = local.cidrs.prd.master
    }
  ]

  ssh_keys = var.ssh_keys

  depends_on = [
    module.wireguard,
    google_compute_network_peering.wireguard_to_dev,
    google_compute_network_peering.wireguard_to_stg,
    google_compute_network_peering.wireguard_to_prd
  ]
}
