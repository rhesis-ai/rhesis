# CloudNativePG Barman: a dedicated GSA for WAL/base backups to GCS, Workload Identity
# binding so CNPG pods authenticate without a JSON key.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

resource "google_project_service" "iamcredentials" {
  project            = var.project_id
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

# account_id: 6-30 chars, alphanum and hyphens
resource "google_service_account" "cnpg_barman" {
  project      = var.project_id
  account_id   = "rhesis-cnpg-bk-${var.environment}"
  display_name = "Rhesis ${var.environment} CNPG Barman (GCS backup)"
  description  = "Uploads Barman / WAL data to the ${var.environment} cnpg backup bucket; authenticates via Workload Identity"

  depends_on = [google_project_service.iamcredentials]
}

# Object read/write/list for Barman WAL and base backups
resource "google_storage_bucket_iam_member" "cnpg_backup_rw" {
  bucket = var.backup_bucket_name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.cnpg_barman.email}"
}

# Bucket metadata read (storage.buckets.get). objectUser alone does not include it;
# the GCS client used by CNPG/Barman checks the bucket before object operations.
resource "google_storage_bucket_iam_member" "cnpg_backup_bucket_viewer" {
  bucket = var.backup_bucket_name
  role   = "roles/storage.bucketViewer"
  member = "serviceAccount:${google_service_account.cnpg_barman.email}"
}

# Workload Identity binding: allows the CNPG cluster's KSA to impersonate this GSA.
# No JSON key is generated — credentials stay inside GCP, nothing in Terraform state.
resource "google_service_account_iam_member" "cnpg_workload_identity" {
  service_account_id = google_service_account.cnpg_barman.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.kubernetes_namespace}/${var.kubernetes_service_account}]"

  depends_on = [google_project_service.iamcredentials]
}
