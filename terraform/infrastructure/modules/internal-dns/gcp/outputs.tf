output "tsig_key_secret_id" {
  description = "Secret Manager secret ID for the TSIG key"
  value       = google_secret_manager_secret.tsig_key.secret_id
}

output "tsig_secret" {
  description = "Base64-encoded TSIG key for BIND9 configuration"
  value       = random_bytes.tsig_key.base64
  sensitive   = true
}

output "tsig_keyname" {
  description = "TSIG key name for RFC2136 dynamic updates"
  value       = "tsig-${var.environment}"
}
