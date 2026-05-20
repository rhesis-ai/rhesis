# WireGuard VPN server in rhesis-platform-admin.
# Peers with dev/stg/prd VPCs cross-project via VPC peering.
# TSIG keys read from each env's remote state (same GCS bucket).
#
# Deploy order:
#   1. envs/dev apply  → creates dev VPC + return-side peering (INACTIVE)
#   2. envs/stg apply  → same for stg
#   3. envs/wireguard apply → creates WireGuard server + peering to dev/stg (both sides ACTIVE)

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {
    prefix = "terraform/infrastructure/envs/wireguard"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  env_enabled = { for env in var.enabled_environments : env => true }
  dev_enabled = lookup(local.env_enabled, "dev", false)
  stg_enabled = lookup(local.env_enabled, "stg", false)
  prd_enabled = lookup(local.env_enabled, "prd", false)
}

# ── WireGuard VPC ────────────────────────────────────────────────────

module "wireguard" {
  source = "../../modules/network/gcp"

  project_id         = var.project_id
  environment        = "wireguard"
  region             = var.region
  network_cidr       = var.network_cidr
  create_gke_subnets = false
}

# ── Remote state: read TSIG keys and VPC self-links from each env ────
# All states share the same GCS bucket; only the prefix differs.

data "terraform_remote_state" "dev" {
  count   = local.dev_enabled ? 1 : 0
  backend = "gcs"
  config = {
    bucket = var.state_bucket
    prefix = "terraform/infrastructure/envs/dev"
  }
}

data "terraform_remote_state" "stg" {
  count   = local.stg_enabled ? 1 : 0
  backend = "gcs"
  config = {
    bucket = var.state_bucket
    prefix = "terraform/infrastructure/envs/stg"
  }
}

data "terraform_remote_state" "prd" {
  count   = local.prd_enabled ? 1 : 0
  backend = "gcs"
  config = {
    bucket = var.state_bucket
    prefix = "terraform/infrastructure/envs/prd"
  }
}

# ── WireGuard server (single NIC — cross-project multi-NIC not supported) ──
# VPC peering handles routing to env VPCs; wireguard_cidr is already
# an authorized master network in each env's GKE cluster.

module "wireguard_server" {
  source = "../../modules/wireguard/gcp"

  project_id          = var.project_id
  region              = var.region
  vpc_name            = module.wireguard.vpc_name
  subnet_self_link    = module.wireguard.subnet_self_links["main"]
  deletion_protection = var.wireguard_deletion_protection
  wireguard_peers     = var.wireguard_peers

  machine_type = local.stg_enabled || local.prd_enabled ? "e2-standard-2" : "e2-medium"

  # Shared VPC NIC in each enabled env's nodes subnet.
  # Gives the WireGuard server a direct layer-3 path to the GKE master —
  # bypassing the non-transitive VPC peering limitation (wireguard → dev → GKE master).
  # Traffic from VPN clients is MASQUERADE'd to the NIC IP before leaving the VM,
  # so GKE master sees source = wireguard_nic_ip (in extra_authorized_cidrs).
  env_nics = concat(
    local.dev_enabled ? [{
      subnet_self_link = data.terraform_remote_state.dev[0].outputs.nodes_subnet_self_link
      network_ip       = local.cidrs.dev.wireguard_nic_ip
      master_cidr      = local.cidrs.dev.master
      environment      = "dev"
      pod_cidr         = local.cidrs.dev.pods
      service_cidr     = local.cidrs.dev.services
      node_cidr        = local.cidrs.dev.nodes
      vpc_name         = data.terraform_remote_state.dev[0].outputs.vpc_name
      project          = data.terraform_remote_state.dev[0].outputs.project_id
    }] : [],
    local.stg_enabled ? [{
      subnet_self_link = data.terraform_remote_state.stg[0].outputs.nodes_subnet_self_link
      network_ip       = local.cidrs.stg.wireguard_nic_ip
      master_cidr      = local.cidrs.stg.master
      environment      = "stg"
      pod_cidr         = local.cidrs.stg.pods
      service_cidr     = local.cidrs.stg.services
      node_cidr        = local.cidrs.stg.nodes
      vpc_name         = data.terraform_remote_state.stg[0].outputs.vpc_name
      project          = data.terraform_remote_state.stg[0].outputs.project_id
    }] : []
  )

  subnet_cidrs = {
    for env, cidr in local.cidrs : env => cidr.network
    if env != "wireguard" && lookup(local.env_enabled, env, false)
  }
  master_cidrs = {
    for env, cidr in local.cidrs : env => cidr.master
    if env != "wireguard" && lookup(local.env_enabled, env, false)
  }

  bind9_tsig_keys = merge(
    local.dev_enabled ? {
      dev = {
        keyname = data.terraform_remote_state.dev[0].outputs.internal_dns_tsig_keyname
        secret  = data.terraform_remote_state.dev[0].outputs.internal_dns_tsig_secret
      }
    } : {},
    local.stg_enabled ? {
      stg = {
        keyname = data.terraform_remote_state.stg[0].outputs.internal_dns_tsig_keyname
        secret  = data.terraform_remote_state.stg[0].outputs.internal_dns_tsig_secret
      }
    } : {},
    local.prd_enabled ? {
      prd = {
        keyname = data.terraform_remote_state.prd[0].outputs.internal_dns_tsig_keyname
        secret  = data.terraform_remote_state.prd[0].outputs.internal_dns_tsig_secret
      }
    } : {}
  )

  bind9_allowed_names = merge(
    local.dev_enabled ? {
      dev = [
        "dev-api.rhesis.ai",
        "dev-app.rhesis.ai",
        "dev-docs.rhesis.ai",
        "dev-chatbot.rhesis.ai",
        "dev-polyphemus.rhesis.ai",
        "dev-argocd.rhesis.ai",
        "dev-grafana.rhesis.ai",
        "dev-telemetry.rhesis.ai",
      ]
    } : {},
    local.stg_enabled ? {
      stg = [
        "stg-api.rhesis.ai",
        "stg-app.rhesis.ai",
        "stg-docs.rhesis.ai",
        "stg-chatbot.rhesis.ai",
        "stg-polyphemus.rhesis.ai",
        "stg-argocd.rhesis.ai",
        "stg-grafana.rhesis.ai",
        "stg-telemetry.rhesis.ai",
      ]
    } : {},
    local.prd_enabled ? {
      prd = [
        "api.rhesis.ai",
        "app.rhesis.ai",
        "docs.rhesis.ai",
        "chatbot.rhesis.ai",
        "polyphemus.rhesis.ai",
        "argocd.rhesis.ai",
        "grafana.rhesis.ai",
        "telemetry.rhesis.ai",
      ]
    } : {}
  )

  depends_on = [module.wireguard]
}

# ── Cross-project VPC peerings: wireguard → each env ────────────────
# The return-side peeerings (env → wireguard) live in each env's main.tf.
# Peering becomes ACTIVE once both sides exist.

resource "google_compute_network_peering" "wireguard_to_dev" {
  count = local.dev_enabled ? 1 : 0

  name         = "peering-wireguard-to-dev"
  network      = module.wireguard.vpc_self_link
  peer_network = data.terraform_remote_state.dev[0].outputs.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [module.wireguard]
}

resource "google_compute_network_peering" "wireguard_to_stg" {
  count = local.stg_enabled ? 1 : 0

  name         = "peering-wireguard-to-stg"
  network      = module.wireguard.vpc_self_link
  peer_network = data.terraform_remote_state.stg[0].outputs.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [module.wireguard]
}

resource "google_compute_network_peering" "wireguard_to_prd" {
  count = local.prd_enabled ? 1 : 0

  name         = "peering-wireguard-to-prd"
  network      = module.wireguard.vpc_self_link
  peer_network = data.terraform_remote_state.prd[0].outputs.vpc_self_link

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  timeouts { create = "15m" }

  depends_on = [module.wireguard]
}
