output "service_account_email" {
  value       = google_service_account.cnpg_barman.email
  description = "Barman GSA; has roles/storage.objectUser on the env CNPG backup bucket"
}

output "service_account_id" {
  value       = google_service_account.cnpg_barman.id
  description = "For IAM debugging"
}
