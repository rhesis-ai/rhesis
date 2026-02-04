output "service_account_email" {
  description = "The email of the service account"
  value       = var.create_service_account ? google_service_account.service_account[0].email : data.google_service_account.existing[0].email
}

output "service_account_id" {
  description = "The ID of the service account"
  value       = var.create_service_account ? google_service_account.service_account[0].id : data.google_service_account.existing[0].id
}

output "service_account_name" {
  description = "The fully-qualified name of the service account"
  value       = var.create_service_account ? google_service_account.service_account[0].name : data.google_service_account.existing[0].name
}

output "key" {
  description = "The service account key (if created)"
  value       = var.create_key ? google_service_account_key.key[0].private_key : null
  sensitive   = true
} 