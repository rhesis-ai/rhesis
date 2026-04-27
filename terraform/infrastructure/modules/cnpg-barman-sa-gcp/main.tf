# CloudNativePG Barman: a dedicated GSA for WAL/base backups to GCS, IAM on the
# env-specific cnpg backup bucket, key material in Secret Manager for the ESO flow.

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

resource "google_project_service" "secretmanager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

# account_id: 6-30 chars, alphanum and hyphens
resource "google_service_account" "cnpg_barman" {
  project      = var.project_id
  account_id   = "rhesis-cnpg-bk-${var.environment}"
  display_name = "Rhesis ${var.environment} CNPG Barman (GCS backup)"
  description  = "Uploads Barman / WAL data to the ${var.environment} cnpg backup bucket; key synced to Secret Manager for ESO"

  depends_on = [google_project_service.iamcredentials]
}

# Read, write, and list objects; sufficient for Barman
resource "google_storage_bucket_iam_member" "cnpg_backup_rw" {
  bucket = var.backup_bucket_name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.cnpg_barman.email}"
}

# Single JSON key; rotate by taint/replace the key resource
resource "google_service_account_key" "cnpg_barman" {
  service_account_id = google_service_account.cnpg_barman.name
}

# Private key: provider gives base64-encoded full JSON; GSM stores raw JSON for the pod
resource "google_secret_manager_secret" "barman_gcs_key" {
  project   = var.project_id
  secret_id = var.secret_manager_secret_id
  labels = {
    purpose     = "cnpg-barman-gcs"
    environment = var.environment
  }
  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "barman_gcs_key" {
  secret = google_secret_manager_secret.barman_gcs_key.id
  # google_service_account_key.private_key: full JSON, base64-encoded
  secret_data = base64decode(google_service_account_key.cnpg_barman.private_key)

  lifecycle {
    # Key rotation creates a new version; avoid drift when key is replaced
    create_before_destroy = true
  }
}
