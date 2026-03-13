resource "google_service_account" "eso" {
  account_id   = "eso-${var.environment}"
  display_name = "External Secrets Operator ${var.environment} service account"
  project      = var.project_id
}

# Project-level secretAccessor: intentional for simplicity so ESO can read any secret
# in this project. For tighter scope, use google_secret_manager_secret_iam_member per secret.
resource "google_project_iam_member" "eso_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.eso.email}"
}

# Workload Identity binding: allow the KSA to impersonate the GSA
resource "google_service_account_iam_member" "eso_workload_identity" {
  service_account_id = google_service_account.eso.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.eso_namespace}/${var.eso_service_account_name}]"
}
