terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

resource "google_project_service" "storage" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_storage_bucket" "file_storage" {
  name     = var.file_storage_bucket_name
  location = var.location
  project  = var.project_id

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  labels = merge(
    var.labels,
    {
      purpose     = "rhesis-backend-files"
      environment = var.environment
    }
  )

  depends_on = [google_project_service.storage]
}

# CloudNativePG (Barman) object store backups for GKE (stg/prd only; disabled when null)
resource "google_storage_bucket" "cnpg_backup" {
  count = var.cnpg_backup_bucket_name == null || var.cnpg_backup_bucket_name == "" ? 0 : 1

  name     = var.cnpg_backup_bucket_name
  location = var.location
  project  = var.project_id

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = var.force_destroy

  versioning {
    enabled = true
  }

  labels = merge(
    var.labels,
    {
      purpose     = "cnpg-backups"
      environment = var.environment
    }
  )

  depends_on = [google_project_service.storage]
}

resource "google_storage_bucket_iam_member" "file_storage" {
  for_each = { for i, m in var.file_storage_iam_members : "${i}" => m }

  bucket = google_storage_bucket.file_storage.name
  role   = each.value.role
  member = each.value.member
}

resource "google_storage_bucket_iam_member" "cnpg_backup" {
  for_each = var.cnpg_backup_bucket_name == null || var.cnpg_backup_bucket_name == "" ? {} : { for i, m in var.cnpg_backup_iam_members : "${i}" => m }

  bucket = google_storage_bucket.cnpg_backup[0].name
  role   = each.value.role
  member = each.value.member
}
