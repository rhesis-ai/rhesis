locals {
  service_account_id = "svc-${var.service_name}-${var.environment}"
}

# Data source to get an existing service account if it exists
data "google_service_account" "existing" {
  count      = var.create_service_account ? 0 : 1
  account_id = local.service_account_id
  project    = var.project_id
}

resource "google_service_account" "service_account" {
  count        = var.create_service_account ? 1 : 0
  account_id   = local.service_account_id
  display_name = "${var.service_name} service account for ${var.environment}"
  description  = "Service account for ${var.service_name} in ${var.environment} environment"
  project      = var.project_id
  
  lifecycle {
    ignore_changes = [
      display_name,
      description
    ]
  }
}

# IAM roles for the service account
resource "google_project_iam_member" "project_roles" {
  for_each = toset(var.roles)
  
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${var.create_service_account ? google_service_account.service_account[0].email : data.google_service_account.existing[0].email}"
}

# Service account key (optional)
resource "google_service_account_key" "key" {
  count              = var.create_key ? 1 : 0
  service_account_id = var.create_service_account ? google_service_account.service_account[0].name : data.google_service_account.existing[0].name
}

# Workload Identity binding (optional)
resource "google_service_account_iam_binding" "workload_identity_binding" {
  count              = length(var.workload_identity_users) > 0 ? 1 : 0
  service_account_id = var.create_service_account ? google_service_account.service_account[0].name : data.google_service_account.existing[0].name
  role               = "roles/iam.workloadIdentityUser"
  members            = var.workload_identity_users
} 