output "file_storage_bucket_name" {
  value       = google_storage_bucket.file_storage.name
  description = "GCS bucket name for backend file storage"
}

output "file_storage_uri" {
  value       = "gs://${google_storage_bucket.file_storage.name}"
  description = "gs:// URI for use in STORAGE_SERVICE_URI"
}

output "cnpg_backup_bucket_name" {
  value       = length(google_storage_bucket.cnpg_backup) > 0 ? google_storage_bucket.cnpg_backup[0].name : null
  description = "GCS bucket name for CNPG backups, or null if not created"
}

output "cnpg_backup_uri" {
  value = (
    length(google_storage_bucket.cnpg_backup) > 0
    ? "gs://${google_storage_bucket.cnpg_backup[0].name}"
    : null
  )
  description = "gs:// URI for CNPG backup destination, or null if not created"
}
