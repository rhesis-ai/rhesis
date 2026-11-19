terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

# Identity the k8s-deploy.yml workflow uses to update the rhesis ArgoCD
# Application's image tags. It patches the Application through the Kubernetes
# API (via Connect Gateway) instead of `argocd app set`, because the API server
# applies a JSON patch with a `test` op atomically: concurrent per-service
# deploys can no longer overwrite each other's tag.
#
# Keyless: GitHub Actions exchanges its OIDC token for this account through the
# shared github-actions pool, so no key exists anywhere. What it may do inside
# the cluster is set by the Role in kubernetes/clusters/<env>/argocd/
# rhesis-deployer-rbac.yaml (get/patch on the rhesis Application only).
data "google_project" "this" {
  project_id = var.project_id
}

resource "google_service_account" "deploy_ci" {
  project      = var.project_id
  account_id   = "deploy-ci-${var.environment}"
  display_name = "Deploy CI (${var.environment})"
  description  = "Identity k8s-deploy.yml federates to from GitHub Actions to set image tags on the rhesis ArgoCD Application."
}

# Same trust as the ArgoCD token it replaces for this step: any workflow in
# the repository. Fork pull requests can't mint OIDC tokens.
resource "google_service_account_iam_member" "github_federation" {
  service_account_id = google_service_account.deploy_ci.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${var.github_wif_pool_name}/attribute.repository/${var.repository}"
}

# Writes through Connect Gateway need gatewayEditor; gatewayReader only proxies
# reads (see the note in modules/connect-gateway/gcp).
resource "google_project_iam_member" "gateway_editor" {
  project = var.project_id
  role    = "roles/gkehub.gatewayEditor"
  member  = "serviceAccount:${google_service_account.deploy_ci.email}"
}
