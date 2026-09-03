# Standalone prd network (no peering). For full deploy with peerings run from infrastructure/

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "4.52.8" # no committed lock file yet (terraform CLI unavailable locally) -- pin exactly
    }
  }
  backend "gcs" {
    prefix = "terraform/infrastructure/envs/prd"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Only used for the cloudflare_ip_ranges data source (modules/kubernetes/gcp),
# not for managing Cloudflare resources -- but the provider mandates some
# credential to initialize regardless of which data source/resource actually
# ends up used, even ip_ranges (which is otherwise a public, unauthenticated
# endpoint). No value set here deliberately: reading the real token via a
# Terraform data source would persist it in plaintext in the state file
# (the provider schema's Sensitive flag only redacts CLI output, not the
# state itself) -- a real secret flowing through Terraform state at all
# breaks this codebase's own pattern elsewhere (ESO, arc-gha: Terraform only
# ever manages placeholders, real values are populated out-of-band via
# `gcloud secrets versions add` and never touch state). CLOUDFLARE_API_TOKEN
# is instead injected as a CI-only env var by terraform-infrastructure.yml
# (fetched via gcloud immediately before plan/apply, never written to a file
# or committed) -- the provider reads it automatically when unset here.
provider "cloudflare" {}

# Live Cloudflare edge IP ranges, fetched at plan/apply time and passed into
# gke_prd's public_ingress_source_ranges below. Lives here (not in
# modules/kubernetes/gcp) so only the one root module that has a real
# Cloudflare credential needs the provider at all -- dev/stg never touch it.
data "cloudflare_ip_ranges" "edge" {}

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
  deletion_protection    = var.gke_deletion_protection

  # prd uses a private endpoint via the WireGuard server's Shared VPC NIC in the prd nodes subnet.
  # The NIC IP (10.6.1.10) is the MASQUERADE'd source for kubectl → GKE master traffic.
  # Explicitly set to guard against a future module-default change accidentally making prd public.
  enable_private_endpoint = true
  extra_authorized_cidrs  = ["${local.cidrs.prd.wireguard_nic_ip}/32"]

  # polyphemus (test-polyphemus.rhesis.ai) is served via ingress-nginx-external,
  # proxied through Cloudflare — restrict to Cloudflare's live edge IP ranges.
  # IPv4 only: this VPC/subnets have no stack_type/dual-stack config anywhere
  # in modules/network or modules/kubernetes, so they're IPv4-only -- adding
  # ipv6_cidr_blocks here would be untested dead weight at best (no IPv6
  # traffic can reach this network to match them).
  enable_public_ingress_firewall = true
  public_ingress_source_ranges   = data.cloudflare_ip_ranges.edge.ipv4_cidr_blocks

  depends_on = [module.prd]
}

module "connect_gateway_prd" {
  source = "../../modules/connect-gateway/gcp"

  project_id  = var.project_id
  environment = "prd"
  cluster_id  = module.gke_prd.cluster_id

  depends_on = [module.gke_prd]
}

module "eso_prd" {
  source = "../../modules/external-secrets/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.gke_prd]
}

# Vertex AI identity owned by this project, so prd's Gemini traffic stops billing
# into playground-437609 via the shared gemini-vertex-sa key.
module "vertex_ai_prd" {
  source = "../../modules/vertex-ai/gcp"

  project_id  = var.project_id
  environment = "prd"
}

module "external_dns_prd" {
  source = "../../modules/external-dns/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

# terraform-prd needs to read the actual Cloudflare token to plan/apply the
# cloudflare provider config (see the comment on provider "cloudflare" above)
# -- roles/editor (already held broadly) does NOT cover Secret Manager's
# "access secret payload" permission, that's deliberately excluded from
# primitive roles and requires this explicit, secret-scoped grant.
#
# member is hardcoded to the terraform-prd@... naming convention rather than
# driven by the TF_SA_PRD GitHub secret (Terraform's root modules have no
# access to GitHub secrets) -- confirmed empirically via
# `gcloud iam service-accounts list` that this is the only custom SA in this
# project matching that pattern, and via an actual `workflow_dispatch` plan
# run against prd that this exact identity is what google-github-actions/auth
# authenticates as here. If TF_SA_PRD is ever rotated to a different SA,
# update this to match -- it will not follow automatically.
#
# prevent_destroy: terraform-infrastructure.yml's "Fetch Cloudflare API token"
# step runs before `terraform init`, with no error handling, so if this grant
# is ever destroyed Terraform can never recreate it for itself -- every
# subsequent prd plan/apply dies on a 403 before Terraform even runs. This is
# a bootstrap prerequisite, not an ordinary managed resource.
#
# This also blocks *replacement*, not just deletion -- e.g. if TF_SA_PRD is
# ever rotated to a different SA and `member` above needs to change. If that
# happens: either grant the new SA's identity out-of-band via `gcloud` first
# (so nothing is ever missing the access), then update `member` and remove
# `prevent_destroy` for that one apply, or temporarily comment it out here.
# Don't just delete this block -- re-add prevent_destroy afterwards.
resource "google_secret_manager_secret_iam_member" "terraform_cloudflare_token_accessor" {
  project   = var.project_id
  secret_id = module.external_dns_prd.cloudflare_api_token_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:terraform-prd@${var.project_id}.iam.gserviceaccount.com"

  lifecycle {
    prevent_destroy = true
  }
}

module "arc_gha_prd" {
  source = "../../modules/arc-gha/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

module "internal_dns_prd" {
  source = "../../modules/internal-dns/gcp"

  project_id  = var.project_id
  environment = "prd"

  depends_on = [module.eso_prd]
}

module "ingress_prd" {
  source = "../../modules/ingress/gcp"

  project_id           = var.project_id
  environment          = "prd"
  region               = var.region
  ilb_subnet_self_link = module.prd.subnet_self_links["ilb"]
  internal_lb_ip       = local.cidrs.prd.ingress_internal_ip

  depends_on = [module.prd]
}

# ── GCS: file storage + CNPG backups ────────────────────────────────
# Previously delegated to the root main.tf, but the root uses a single provider/project
# which conflicts with the multi-project layout. Managed here instead.

module "gcs_prd" {
  source = "../../modules/storage-buckets/gcp"

  project_id  = var.project_id
  environment = "prd"
  location    = var.region

  file_storage_bucket_name = var.file_storage_bucket_name
  cnpg_backup_bucket_name  = var.cnpg_backup_bucket_name
  force_destroy            = var.force_destroy
  file_storage_iam_members = []
  cnpg_backup_iam_members  = []
}

# CloudNativePG Barman: GSA + Workload Identity binding for WAL/base backups.
# Secret IDs must match kubernetes/clusters/prd/rhesis/cnpg-gcs-externalsecret.yaml
module "cnpg_barman_prd" {
  source = "../../modules/cnpg-barman-sa-gcp"

  project_id                 = var.project_id
  environment                = "prd"
  backup_bucket_name         = var.cnpg_backup_bucket_name
  kubernetes_service_account = "rhesis-prd"

  depends_on = [module.gcs_prd, module.gke_prd]
}

# ArgoCD bootstrap is done locally via VPN after GKE is up.

# ── Shared VPC: prd project is the host, rhesis-platform-admin is a service project ──────────
# This allows the WireGuard server (in rhesis-platform-admin) to attach a NIC directly into
# the prd nodes subnet, bypassing GCP's non-transitive peering limitation. Same pattern as dev
# previously used; rhesis-platform-admin can only be a service project of ONE host at a time,
# so dev's Shared VPC host relationship must be removed before applying this.
#
# Subnet user grants are required for:
#   - terraform-wireguard SA: creates the VM NIC during terraform apply
#   - rhesis-platform-admin default compute SA: runtime access by the VM itself

data "google_project" "platform_admin" {
  project_id = "rhesis-platform-admin"
}

resource "google_compute_shared_vpc_host_project" "prd" {
  project = var.project_id
}

resource "google_compute_shared_vpc_service_project" "platform_admin" {
  host_project    = var.project_id
  service_project = "rhesis-platform-admin"
  depends_on      = [google_compute_shared_vpc_host_project.prd]
}

resource "google_compute_subnetwork_iam_member" "wireguard_tf_sa_subnet_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = module.prd.subnet_self_links["nodes"]
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:terraform-wireguard@rhesis-platform-admin.iam.gserviceaccount.com"
  depends_on = [google_compute_shared_vpc_host_project.prd]
}

resource "google_compute_subnetwork_iam_member" "wireguard_compute_sa_subnet_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = module.prd.subnet_self_links["nodes"]
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:${data.google_project.platform_admin.number}-compute@developer.gserviceaccount.com"
  depends_on = [google_compute_shared_vpc_host_project.prd]
}

# Allow DNS (port 53) from GKE nodes/pods to the WireGuard server's BIND9 resolver.
# Managed here (not in the wireguard module) because TF_SA_WIREGUARD lacks firewall
# permissions in this project — TF_SA_PRD already has them.
resource "google_compute_firewall" "wireguard_dns" {
  name     = "wireguard-allow-dns-prd"
  network  = module.prd.vpc_name
  project  = var.project_id
  priority = 900

  allow {
    protocol = "tcp"
    ports    = ["53"]
  }
  allow {
    protocol = "udp"
    ports    = ["53"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [local.cidrs.prd.nodes, local.cidrs.prd.pods]
  target_tags   = ["wireguard-server"]

  depends_on = [module.prd]
}

# ── Return-side peering: prd VPC → wireguard VPC (cross-project) ────
# Required for BIND9/DNS routing from GKE pods and for kubectl via WireGuard VPN.
# Both sides must exist for ACTIVE state.
resource "google_compute_network_peering" "prd_to_wireguard" {
  name         = "peering-prd-to-wireguard"
  network      = module.prd.vpc_self_link
  peer_network = "https://www.googleapis.com/compute/v1/projects/rhesis-platform-admin/global/networks/vpc-wireguard"

  import_subnet_routes_with_public_ip = true
  export_subnet_routes_with_public_ip = true

  # prd is the ONLY peering exchanging custom routes; dev and stg are false. That asymmetry
  # was enabled out of band and is pinned here rather than left to the provider default, so
  # it is visible in code and cannot silently revert on the next apply.
  #
  # It is inert today: no VPC contains a custom route to export. The wireguard VPC learns
  # prd's subnet and master CIDRs (10.6.0.0/23, 10.6.4.0/28, 10.7.0.0/17) through ordinary
  # subnet-route exchange -- the two flags above -- exactly as it does for dev and stg with
  # this off. Do not "tidy" it to false on the assumption it is dead: the matching
  # import_custom_routes = true on the wireguard side is pinned too, and turning the pair
  # off is a separate decision.
  #
  # What would make it load-bearing is modules/gateway/gcp/, which is never instantiated.
  # That module exports a VM-next-hop route for the GKE master CIDR, and GCP only propagates
  # such a route over a peering when custom-route exchange is on.
  export_custom_routes = true

  timeouts { create = "15m" }

  depends_on = [module.prd]
}

# Generate cluster.env for ingress-nginx-internal (single source of truth)
resource "local_file" "cluster_env_prd" {
  content              = <<-EOT
# Generated by Terraform from terraform/infrastructure/envs/prd. Do not edit by hand.
region=${var.region}
ilb-subnet-name=${module.prd.ilb_subnet_name}
internal-lb-ip=${local.cidrs.prd.ingress_internal_ip}
EOT
  filename             = "${path.module}/../../../../kubernetes/clusters/prd/ingress-nginx-internal/cluster.env"
  file_permission      = "0644"
  directory_permission = "0755"
}

# ── Adopt resources that were created by hand in prd ─────────────────
# dev and stg went through Terraform; prd did not. Proof: dev's and stg's
# <env>-arc-github-app-id hold the module's literal "PLACEHOLDER_GITHUB_APP_ID" in version 1
# with the real value added later as version 2, while prd has a single version holding the
# real value. So prd's secrets were created with `gcloud secrets create` and Terraform never
# owned them, which is why this root planned 8 spurious creates while dev and stg planned
# clean.
#
# Importing the VERSION resources is mandatory, not tidiness. prd's ARC secrets feed the
# arc-runners/arc-github-app-secret ExternalSecret, which drives live self-hosted runners.
# If Terraform created the placeholder versions instead, each would become `latest` and ESO
# would sync "PLACEHOLDER_GITHUB_APP_ID" into the cluster within its 1h refresh, breaking
# prd CI. Importing is safe because modules/arc-gha/gcp/main.tf sets
# `ignore_changes = [secret_data]` on all three, so the imported real value is never
# rewritten back to the placeholder.
#
# Note the id formats differ by resource type, and this is easy to get wrong: secrets use
# the project ID, versions use the project NUMBER (969193216701). Both were taken from the
# `id` attributes Terraform already stored for the equivalent dev resources rather than
# inferred, so they match what the provider writes to state.
#
# Terraform drops an import block once applied, so delete this whole section after the first
# successful apply.

import {
  to = module.arc_gha_prd.google_secret_manager_secret.arc_github_app_id
  id = "projects/rhesis-prd/secrets/prd-arc-github-app-id"
}

import {
  to = module.arc_gha_prd.google_secret_manager_secret.arc_github_app_installation_id
  id = "projects/rhesis-prd/secrets/prd-arc-github-app-installation-id"
}

import {
  to = module.arc_gha_prd.google_secret_manager_secret.arc_github_app_private_key
  id = "projects/rhesis-prd/secrets/prd-arc-github-app-private-key"
}

import {
  to = module.arc_gha_prd.google_secret_manager_secret_version.arc_github_app_id_placeholder
  id = "projects/969193216701/secrets/prd-arc-github-app-id/versions/1"
}

import {
  to = module.arc_gha_prd.google_secret_manager_secret_version.arc_github_app_installation_id_placeholder
  id = "projects/969193216701/secrets/prd-arc-github-app-installation-id/versions/1"
}

import {
  to = module.arc_gha_prd.google_secret_manager_secret_version.arc_github_app_private_key_placeholder
  id = "projects/969193216701/secrets/prd-arc-github-app-private-key/versions/1"
}

import {
  to = module.connect_gateway_prd.google_secret_manager_secret.mint_destination
  id = "projects/rhesis-prd/secrets/prd-rhesis-selfhosted-license-mint"
}

# Deliberately NOT imported:
# module.connect_gateway_prd.google_secret_manager_secret_iam_member.ci_manage_mint_destination
# does not exist in prd -- the mint secret only carries the workflow-granted
# secretVersionAdder for the default compute SA, while dev and stg both have
# roles/secretmanager.admin for their license-ci-<env>@. Letting Terraform create it brings
# prd in line with the other two, so it is a legitimate create rather than drift.
