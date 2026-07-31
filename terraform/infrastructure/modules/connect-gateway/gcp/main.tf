terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# Registers this environment's GKE cluster with GKE Hub (Fleet) and creates a
# dedicated, narrowly-scoped service account for rhesis-ee's licensing CI
# workflows to reach it through Connect Gateway.
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
#
# The service account: an earlier version of this module took an existing
# service account email as an input and granted gatewayReader to it, with
# terraform-<env> passed in at the call site -- convenient (that identity
# already exists and is already what CI authenticates as for other things),
# but terraform-<env> holds roles/editor + roles/iam.securityAdmin +
# roles/resourcemanager.projectIamAdmin on the whole project (verified via
# `gcloud projects get-iam-policy`, identical across dev/stg/prd) --
# effectively full project control. rhesis-ee's license-issue.yml and
# license-mint-selfhosted.yml authenticate with a static, long-lived
# GCP_SA_KEY (not WIF, unlike this repo's own terraform-infrastructure.yml),
# stored as a secret in a *different* repository. A leaked key would hand
# out near-owner access to the whole GCP project, for a task that only ever
# needs to create Jobs in one K8s namespace, read two Secret Manager entries,
# and run a Cloud Run Job -- so this module now creates its own SA instead,
# scoped to exactly that.
resource "google_service_account" "license_ci" {
  project      = var.project_id
  account_id   = "license-ci-${var.environment}"
  display_name = "License issuance/mint CI (rhesis-ee)"
  description  = "Identity rhesis-ee's license-issue.yml / license-mint-selfhosted.yml authenticate as via GCP_SA_KEY. Scoped to exactly what those workflows do -- see the roles granted alongside this resource."
}

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

# Reach the cluster via Connect Gateway.
resource "google_project_iam_member" "ci_gateway_reader" {
  project = var.project_id
  role    = "roles/gkehub.gatewayReader"
  member  = "serviceAccount:${google_service_account.license_ci.email}"

  depends_on = [google_project_service.connectgateway]
}

# Read the signing key + kid (license-issue.yml, license-mint-selfhosted.yml),
# and create/manage the self-hosted mint destination secret
# (license-mint-selfhosted.yml's "Ensure destination secret exists..." step
# -- the secret doesn't exist on first use, so this can't be scoped to a
# specific secret resource the way a plain secretAccessor grant could be).
resource "google_project_iam_member" "ci_secretmanager_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.license_ci.email}"
}

# Resolve the "latest" backend image tag (both workflows' "Resolve image
# tag" step) from Artifact Registry.
resource "google_project_iam_member" "ci_artifactregistry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.license_ci.email}"
}

# license-mint-selfhosted.yml deploys/executes a Cloud Run Job.
resource "google_project_iam_member" "ci_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.license_ci.email}"
}

# The mint Cloud Run Job sets no --service-account, so it runs as the
# project's default compute SA -- deploying a job that will run as a given
# SA requires the deployer to hold serviceAccountUser on that SA specifically
# (scoped to the one resource, not roles/iam.serviceAccountUser at the
# project level, which would let this identity act as *any* SA in the
# project).
data "google_project" "this" {
  project_id = var.project_id
}

resource "google_service_account_iam_member" "ci_act_as_default_compute" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.google_project.this.number}-compute@developer.gserviceaccount.com"
  role                = "roles/iam.serviceAccountUser"
  member              = "serviceAccount:${google_service_account.license_ci.email}"
}
