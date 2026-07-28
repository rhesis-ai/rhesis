terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# Registers this environment's GKE cluster with GKE Hub (Fleet) and grants
# the CI service account permission to reach it through Connect Gateway.
#
# Why this exists: dev/stg/prd clusters are private, with the API server
# reachable only from the WireGuard VPN CIDR (see modules/kubernetes/gcp's
# master_authorized_networks_config). GitHub-hosted runners aren't on that
# VPN, and self-hosted ARC runners (modules/arc-gha) are registered per-repo
# against rhesis-ai/rhesis specifically -- a workflow living in a different
# repo (e.g. rhesis-ee) can never have its jobs picked up by them. Connect
# Gateway proxies kubectl/gcloud calls over HTTPS using IAM auth instead of
# network-level access, so any CI identity holding roles/gkehub.gatewayReader
# can reach the cluster with a plain `gcloud container fleet memberships
# get-credentials` call -- no VPN, no self-hosted runner, from any repo.
#
# Once this is applied, the actual kubeconfig command is:
#   gcloud container fleet memberships get-credentials ${var.environment} \
#     --project=${var.project_id}
# followed by ordinary kubectl, authorized by whatever Kubernetes RBAC
# (Role/RoleBinding) already exists for the calling identity -- Connect
# Gateway only replaces *network* reachability, not authorization.

resource "google_project_service" "gkehub" {
  project            = var.project_id
  service            = "gkehub.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "connectgateway" {
  project            = var.project_id
  service            = "connectgateway.googleapis.com"
  disable_on_destroy = false
}

resource "google_gke_hub_membership" "cluster" {
  membership_id = var.environment
  project       = var.project_id
  location      = "global"

  endpoint {
    gke_cluster {
      resource_link = "//container.googleapis.com/${var.cluster_id}"
    }
  }

  depends_on = [google_project_service.gkehub]
}

resource "google_project_iam_member" "ci_gateway_reader" {
  project = var.project_id
  role    = "roles/gkehub.gatewayReader"
  member  = "serviceAccount:${var.ci_service_account_email}"

  depends_on = [google_project_service.connectgateway]
}
