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

# Reach the cluster via Connect Gateway. gatewayReader alone
# (gkehub.gateway.generateCredentials/get + gkehub.memberships.get) is not
# sufficient -- `gcloud container fleet memberships get-credentials` also
# needs gkehub.memberships.list, confirmed empirically against a live
# license-issue.yml run (PERMISSION_DENIED on 'gkehub.memberships.list').
# gkehub.viewer covers that; it's read-only (no mutation permissions on
# Fleet/membership resources), so this adds visibility, not write access.
resource "google_project_iam_member" "ci_gateway_reader" {
  project = var.project_id
  role    = "roles/gkehub.gatewayReader"
  member  = "serviceAccount:${google_service_account.license_ci.email}"

  depends_on = [google_project_service.connectgateway]
}

resource "google_project_iam_member" "ci_gkehub_viewer" {
  project = var.project_id
  role    = "roles/gkehub.viewer"
  member  = "serviceAccount:${google_service_account.license_ci.email}"

  depends_on = [google_project_service.connectgateway]
}

# Secret Manager access is scoped per-secret, not project-wide -- peqy
# correctly flagged an earlier version of this module granting
# roles/secretmanager.admin at the project level as still too broad a blast
# radius for a long-lived key sitting in a different repository's secrets.
# The signing key + kid are managed entirely out-of-band (not Terraform
# resources anywhere in this repo -- `gcloud secrets create`/`versions add`,
# manually), so they're referenced here by their literal, predictable
# secret_id rather than a resource reference; that's fine, IAM bindings
# don't require the target to be Terraform-managed.
resource "google_secret_manager_secret_iam_member" "ci_read_private_key" {
  project   = var.project_id
  secret_id = "${var.environment}-rhesis-rhesis-license-private-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.license_ci.email}"
}

resource "google_secret_manager_secret_iam_member" "ci_read_kid" {
  project   = var.project_id
  secret_id = "${var.environment}-rhesis-rhesis-license-kid"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.license_ci.email}"
}

# license-mint-selfhosted.yml's destination secret. Pre-created here
# (Terraform-managed, no initial version -- the Cloud Run job writes the
# actual token at runtime) specifically so the CI identity never needs
# project-wide secretmanager.secrets.create: the workflow's own "Ensure
# destination secret exists" step already checks `gcloud secrets describe`
# first and only creates on a cache miss, so once this exists that branch is
# permanently a no-op.
resource "google_secret_manager_secret" "mint_destination" {
  project   = var.project_id
  secret_id = "${var.environment}-rhesis-selfhosted-license-mint"

  replication {
    auto {}
  }
}

# admin (not just accessor), scoped to this one Terraform-created secret --
# the workflow's "Ensure destination secret exists" step also calls
# `gcloud secrets add-iam-policy-binding` on every run (granting the Cloud
# Run job's runtime SA secretVersionAdder), which needs setIamPolicy. Bound
# at the secret level, not the project level, so this grants no access to
# any other secret.
resource "google_secret_manager_secret_iam_member" "ci_manage_mint_destination" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.mint_destination.secret_id
  role      = "roles/secretmanager.admin"
  member    = "serviceAccount:${google_service_account.license_ci.email}"
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
