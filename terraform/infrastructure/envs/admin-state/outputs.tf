output "state_bucket" {
  description = "The managed Terraform state bucket."
  value       = google_storage_bucket.state.name
}

output "versioning_enabled" {
  description = "Whether object versioning is on (rollback for state)."
  value       = google_storage_bucket.state.versioning[0].enabled
}
