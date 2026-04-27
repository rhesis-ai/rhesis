output "service_account_email" {
  value       = google_service_account.cnpg_barman.email
  description = "Barman GSA; has roles/storage.objectUser on the env CNPG backup bucket"
}

output "secret_manager_secret_id" {
  value       = google_secret_manager_secret.barman_gcs_key.secret_id
  description = "GSM name for the JSON key (matches ESO remoteRef for cnpg-gcs-externalsecret)"
}

output "service_account_id" {
  value       = google_service_account.cnpg_barman.id
  description = "For IAM debugging"
}
